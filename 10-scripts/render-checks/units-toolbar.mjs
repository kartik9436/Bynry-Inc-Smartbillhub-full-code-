/**
 * DEF-782 (this screen) and DEF-783 (the shared label rule it uncovered) ·
 * r11 step 2d — **PROVE IT BY CLICKING** (hard-won law 6: no gate in this repo
 * looks at rendered output, and nine defects were found this way and by nothing
 * else).
 *
 * PRM-01U — the Units list (S15) — measured against `05-prototype/r10-2026-08-16/
 * SMARTBillHub.dc.html` lines 687-714, after the PO put the deployed screen and
 * r10's beside each other: *"also can you see this Unit landing screen - search,
 * filter, colume filter, description ... can you correct the ui"* (2026-08-26).
 *
 * WHY THIS IS NOT A VITEST FILE, and it is not a preference. Every claim this
 * lane makes is GEOMETRIC — *is the control row ONE row*, *does the segment sit
 * on it*, *is the premises picker 208px or 554px wide*. jsdom has no layout
 * engine: `UnitsPage.test.tsx` rendered the identical markup green through the
 * entire three-row regression and could not have seen it. The numbers this
 * script prints are the whole point:
 *
 *   toolbar height   BEFORE 156px (four bands)   AFTER 36px (one)
 *   premises picker  BEFORE y=367 w=554          AFTER y=295 w=208
 *   scoped toolbar   BEFORE 156px, no chip       AFTER  80px, chip + ✕
 *   whole run        BEFORE 17/28                AFTER  29/29
 *
 * ⚠ THE `⇅` COUNT IS NOT A BUG AND IS ASSERTED LOW ON PURPOSE. r10 paints the
 * glyph on EVERY non-empty header (`styles.css`: `.lt thead th:not(:empty)::after
 * {content:" ⇅"}`) — a blanket rule, not a capability list. `UNIT_SORTS` is
 * `unit_no · premise · label · type` and the server sorts nothing else, so four
 * sort controls is BR-SHL-010 obeyed ("an undeclared capability never renders"),
 * not eight minus four.
 *
 * The twelve fixture rows ARE r10's twelve, field for field, so a column that
 * silently stops rendering shows up as a missing sentence rather than as an
 * empty table.
 *
 * RUN (from the REPO ROOT):
 *   (cd 07-frontend && npx vite build)
 *   (cd 07-frontend && PORT=4327 API_PROXY_TARGET= node server.mjs &)
 *   node 10-scripts/render-checks/units-toolbar.mjs
 *
 * The API is answered by Playwright route interception. Exits non-zero on any
 * failed check.
 */
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const FE = process.env.SBH_FE ?? path.resolve("07-frontend");
const requireFrontend = createRequire(path.join(FE, "package.json"));
const { chromium } = requireFrontend("playwright-core");

function findChromium() {
  if (process.env.SBH_CHROMIUM) return process.env.SBH_CHROMIUM;
  const wanted = chromium.executablePath();
  if (fs.existsSync(wanted)) return wanted;
  const root = process.env.PLAYWRIGHT_BROWSERS_PATH ?? "/opt/pw-browsers";
  for (const dir of fs.existsSync(root) ? fs.readdirSync(root) : []) {
    if (!dir.startsWith("chromium")) continue;
    for (const rel of ["chrome-linux/chrome", "chrome"]) {
      const c = path.join(root, dir, rel);
      if (fs.existsSync(c)) return c;
    }
  }
  return wanted;
}

const BASE = process.env.SBH_BASE ?? "http://127.0.0.1:4327";
const TENANT = "brazosbend";
const SHOT = process.env.SBH_SHOTS ?? path.resolve("07-frontend/dist");
fs.mkdirSync(SHOT, { recursive: true });
const TAG = process.env.SBH_TAG ?? "after";

const PERMISSIONS = {
  role: "system_admin",
  role_name: "System Admin",
  permissions: [{ code: "premises_accounts", label: "Premises / Accounts", access: "Full" }],
};

// r10's own twelve rows, field for field (SMARTBillHub.dc.html lines 699-712).
const R10 = [
  ["U-10432-A", "P-10432", "1408 Elm St", "Unit A", "residential", ["electric","water"], [["M-4021",null],["M-4022",null]], "occupied", "Miller, Sarah", "A-10432", "active"],
  ["U-10432-B", "P-10432", "1408 Elm St", "Unit B", "residential", ["electric","water"], [["M-4023",null],["M-4024",null]], "vacant", null, null, "vacant"],
  ["U-10891", "P-10891", "2201 Cedar Ln", null, "residential", ["electric","water","sewer"], [["M-4108",null],["M-4109",null]], "occupied", "Chen, David", "A-10891", "active"],
  ["U-11024-200", "P-11024", "500 Main Plaza", "Suite 200", "commercial", ["electric","water"], [["M-4204","sub"]], "occupied", "Ridge Coffee Co.", "A-11024", "active"],
  ["U-11024-210", "P-11024", "500 Main Plaza", "Suite 210", "commercial", ["electric"], [["M-4205","sub"]], "occupied", "Blueprint Studio", "A-11025", "active"],
  ["U-11024-M", "P-11024", "500 Main Plaza", "Master", "commercial_master", ["electric","water"], [["M-4200","master"]], "occupied", "Main St. Holdings", "A-11020", "active"],
  ["U-11312", "P-11312", "3450 Oak Ridge", null, "residential", ["electric","water"], [["M-4518",null],["M-4519",null]], "occupied", "Rodriguez, M.", "A-11512", "pending"],
  ["U-11340", "P-11340", "77 Industrial", "Bldg 1", "commercial", ["electric","water","sewer"], [["M-4310",null],["M-4311",null],["M-4312",null]], "occupied", "Northwind Mfg.", "A-11340", "active"],
  ["U-11455", "P-11455", "901 Hillside", null, "residential", ["electric","water"], [["M-4412",null],["M-4413",null]], "occupied", "Park, Jenna", "A-11455", "marked_disconnect"],
  ["U-11602-101", "P-11602", "2200 Riverside", "Apt 101", "residential_submetered", ["electric"], [["M-5001","sub"]], "occupied", "Nguyen, T.", "A-12010", "active"],
  ["U-11602-102", "P-11602", "2200 Riverside", "Apt 102", "residential_submetered", ["electric"], [["M-5002","sub"]], "occupied", "Patel, R.", "A-12011", "active"],
  ["U-11602-103", "P-11602", "2200 Riverside", "Apt 103", "residential_submetered", ["electric"], [["M-5003","sub"]], "vacant", null, null, "vacant"],
];

const UNITS = R10.map((r, i) => ({
  id: `u-${i + 1}`,
  unit_no: r[0],
  premises_id: `p-${r[1]}`,
  premise_no: r[1],
  premise_address: r[2],
  label: r[3],
  unit_type: r[4],
  floor_label: null,
  square_feet: null,
  rate_plan_id: i === 6 ? null : "plan-1",
  plan_effective_from: "2026-01-01",
  plan_locked: false,
  vacant_standby_auto: false,
  is_common_area: false,
  services: r[5],
  active: true,
  metered_services: r[5],
  meters: r[6].map(([no, q], k) => ({ id: `m-${i}-${k}`, asset_no: no, qualifier: q })),
  occupancy: r[7],
  occupant: r[8],
  account_no: r[9],
  status: r[10],
  sub_metered: r[6].some(([, q]) => q === "sub"),
}));

const PREMISES = [...new Map(R10.map((r) => [r[1], { premise_no: r[1], address: r[2] }])).values()].map(
  (p, i) => ({
    id: `p-${p.premise_no}`,
    premise_no: p.premise_no,
    address_line: p.address,
    city: "Brazos Bend",
    state: "TX",
    postal_code: "77000",
    premises_type: "residential",
    premises_type_label: "Residential",
    units: 2,
    common_area_units: 0,
    services: ["electric", "water"],
    owner_name: "Owner " + i,
    status: "active",
    active: true,
  }),
);

const calls = [];
const prefs = new Map();

function ok(body, status = 200) {
  return { status, contentType: "application/json", body: body === null ? "" : JSON.stringify(body) };
}

function answer(url, method, postData) {
  const u = new URL(url);
  const p = u.pathname;
  calls.push(`${method} ${p}`);
  if (p.includes("/user-preferences/")) {
    const key = decodeURIComponent(p.split("/user-preferences/")[1]);
    if (method === "PUT") {
      prefs.set(key, JSON.parse(postData ?? "{}").value);
      return ok({ key, value: prefs.get(key) });
    }
    return ok({ key, value: prefs.has(key) ? prefs.get(key) : null });
  }
  if (p.endsWith("/settings/services")) {
    // BR-MET-003 — the tenant's enabled set, which is what the `service` filter
    // group is allowed to offer. `thermal` is DISABLED here on purpose: an
    // option list that includes it is reading `enabled` wrong.
    return ok([
      { service: "electric", name: "Electric", enabled: true, primary_uom: "kWh", alt_uom: null, revenue_account: null, base_revenue_account: null, rate_schedules: 1, accounts: 1 },
      { service: "water", name: "Water", enabled: true, primary_uom: "gal", alt_uom: null, revenue_account: null, base_revenue_account: null, rate_schedules: 1, accounts: 1 },
      { service: "sewer", name: "Sewer", enabled: true, primary_uom: "gal", alt_uom: null, revenue_account: null, base_revenue_account: null, rate_schedules: 1, accounts: 1 },
      { service: "thermal", name: "Thermal / Heat", enabled: false, primary_uom: null, alt_uom: null, revenue_account: null, base_revenue_account: null, rate_schedules: 0, accounts: 0 },
    ]);
  }
  if (p.endsWith("/me/permissions")) return ok(PERMISSIONS);
  if (p.endsWith("/me")) return ok({ id: "user-1", full_name: "A. Clerk", email: "a@b.test", tenant: TENANT });
  if (p.endsWith("/units")) {
    let rows = UNITS;
    const q = (u.searchParams.get("q") ?? "").toLowerCase();
    if (q !== "") {
      rows = rows.filter((r) =>
        [r.premise_no, r.premise_address, r.label, ...r.meters.map((m) => m.asset_no)]
          .filter(Boolean).join(" ").toLowerCase().includes(q));
    }
    const occ = u.searchParams.get("f.occupancy");
    if (occ === "occupied" || occ === "vacant") rows = rows.filter((r) => r.occupancy === occ);
    if (occ === "sub_metered") rows = rows.filter((r) => r.sub_metered);
    const prem = u.searchParams.get("f.premises_id");
    if (prem) rows = rows.filter((r) => r.premises_id === prem);
    return ok({ count: rows.length, next: null, previous: null, results: rows });
  }
  if (p.endsWith("/premises")) {
    return ok({
      count: PREMISES.length, next: null, previous: null, results: PREMISES,
      rollup: { premises: 1247, units: 3120, common_area_units: 18, unplanned_units: 4, accounts: 2980, services: 5 },
    });
  }
  return ok({ count: 0, next: null, previous: null, results: [] });
}

const checks = [];
function check(name, pass, detail = "") {
  checks.push({ name, pass, detail });
  console.log(`${pass ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
}

const browser = await chromium.launch({ executablePath: findChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
page.on("pageerror", (e) => console.log("PAGEERROR", e.message));
await page.route("**/api/**", async (route) => {
  const r = route.request();
  await route.fulfill(answer(r.url(), r.method(), r.postData()));
});

await page.goto(`${BASE}/${TENANT}/premises/units`, { waitUntil: "networkidle" });
await page.locator("table.data-table, table").first().waitFor({ state: "visible", timeout: 20000 });
await page.waitForTimeout(600);

// ── 1 · The UNIT column ────────────────────────────────────────────────────
const headers = await page.locator("thead th").allInnerTexts();
const clean = headers.map((h) => h.replace(/[⇅▲▼]/g, "").trim()).filter((h) => h !== "");
console.log("HEADERS:", JSON.stringify(clean));
check(
  "r10's UNIT column is rendered (the label within the premise)",
  clean.some((h) => h.toLowerCase() === "unit"),
  clean.join(" | "),
);
const bodyText = await page.locator("tbody").innerText();
for (const want of ["Unit A", "Suite 200", "Master", "Apt 101"]) {
  check(`the unit label \`${want}\` reaches the screen`, bodyText.includes(want));
}

// ── 2 · r10's eight columns are all present, in r10's order ────────────────
const R10_COLS = ["Unit ID", "Premise", "Unit", "Type", "Services", "Meters", "Occupant / Account", "Status"];
const lower = clean.map((h) => h.toLowerCase());
const idx = R10_COLS.map((c) => lower.indexOf(c.toLowerCase()));
check("every r10 column is present", idx.every((i) => i >= 0), JSON.stringify(R10_COLS.filter((c, k) => idx[k] < 0)));
check(
  "and they appear in r10's order",
  idx.every((v, k) => k === 0 || (v > idx[k - 1] && v >= 0)),
  JSON.stringify(idx),
);

// ── 3 · The search placeholder is THIS list's prompt (B14 rule 19) ─────────
const tbSearch = page.locator('.table-toolbar input[type="search"]').first();
const ph = await tbSearch.getAttribute("placeholder");
check(
  'the search box says r10\'s "Search premises, units, meters…", not "Search this list"',
  ph === "Search premises, units, meters…",
  JSON.stringify(ph),
);
const al = await tbSearch.getAttribute("aria-label");
check("its accessible name is the SAME sentence (B14 rule 19)", al === ph, JSON.stringify(al));

// ── 4 · ONE control row (r10 draws one `.toolbar`) ─────────────────────────
const tb = page.locator(".table-toolbar").first();
const tbBox = await tb.boundingBox();
const kids = tb.locator(":scope > *");
const n = await kids.count();
const tops = [];
for (let i = 0; i < n; i++) {
  const b = await kids.nth(i).boundingBox();
  if (b && b.width > 0) tops.push(Math.round(b.y));
}
// ONE ROW is a geometric fact, not a count of distinct `y` values: every
// visible control's box must fit inside the toolbar's FIRST control-height
// band. A control that wrapped starts below it, whatever its exact top.
const CONTROL_BAND = 46; // one 36px control + its focus ring, generously
const overflow = [];
for (let i = 0; i < n; i++) {
  const b = await kids.nth(i).boundingBox();
  if (b && b.width > 0 && tbBox && b.y + b.height > tbBox.y + CONTROL_BAND) {
    overflow.push(`${Math.round(b.y - tbBox.y)}..${Math.round(b.y + b.height - tbBox.y)}`);
  }
}
console.log("TOOLBAR child tops:", JSON.stringify(tops), "height", tbBox && Math.round(tbBox.height));
check(
  "the control row is ONE row (r10's single `.toolbar`) — nothing wraps below the first band",
  overflow.length === 0,
  overflow.length === 0 ? `${Math.round(tbBox?.height ?? -1)}px tall` : `${overflow.length} control(s) below the band: ${overflow.join(", ")}`,
);
check("the toolbar is one control-height band (<= 46px)", (tbBox?.height ?? 999) <= CONTROL_BAND, `${Math.round(tbBox?.height ?? -1)}px`);

// ── 5 · The occupancy segment is right-aligned on that same row ────────────
const seg = page.locator('[role="radiogroup"], .seg').first();
const segBox = await seg.boundingBox();
check(
  "the All/Occupied/Vacant/Sub-metered segment sits on the control row",
  !!segBox && !!tbBox && Math.abs(segBox.y - tbBox.y) < 24,
  `seg.y=${Math.round(segBox?.y ?? -1)} toolbar.y=${Math.round(tbBox?.y ?? -1)}`,
);
check(
  "and it is right-aligned (r10: the segment ends at the toolbar's right edge)",
  !!segBox && !!tbBox && segBox.x + segBox.width > tbBox.x + tbBox.width - 220,
  `seg right=${Math.round((segBox?.x ?? 0) + (segBox?.width ?? 0))} toolbar right=${Math.round((tbBox?.x ?? 0) + (tbBox?.width ?? 0))}`,
);

// ── 6 · The premise picker is not a full-width box on its own row ──────────
const premiseBox = await page.locator("#f\\.premises_id").first().boundingBox().catch(() => null);
check(
  "the Premise picker does not occupy a row of its own",
  !premiseBox || (!!tbBox && Math.abs(premiseBox.y - tbBox.y) < 40),
  premiseBox ? `y=${Math.round(premiseBox.y)} w=${Math.round(premiseBox.width)}` : "absent",
);

// ── 7 · Every header carries a sort affordance where it sorts ──────────────
const sortables = await page.locator("thead th button").count();
check("sortable headers are buttons with a direction affordance", sortables >= 4, `${sortables} sort buttons`);

// ── 8 · The description (B14: 80%) ─────────────────────────────────────────
const exp = page.locator(".page-header-explainer").first();
const expText = (await exp.count()) ? await exp.innerText() : "";
check(
  "the Units explainer is r10's own sentence",
  expText.startsWith("A unit is a metered space inside a premise"),
  JSON.stringify(expText.slice(0, 60)),
);

// ── 9 · The ruled additions SURVIVE (they are not r10 drift) ───────────────
check("the SELECT checkbox column is still there (BR-MET-041 bulk plan)",
  (await page.locator('tbody input[type="checkbox"]').count()) > 0);
check("the ACTIONS icon column is still there (B14 rule 15)",
  (await page.locator("tbody [data-row-actions], tbody button[aria-label], tbody button[title]").count()) > 0);
check("Download CSV is still offered (US-MET-002 capability row, IS-9)",
  (await page.getByRole("button", { name: /download|csv|export/i }).count()) > 0);


// ── 10 · The column chooser (the PO's "colume filter") ────────────────────
const chooser = page.locator(".table-toolbar details").last();
await chooser.locator("summary").click();
await page.waitForTimeout(250);
const chooserText = await chooser.locator("div").first().innerText();
check("the ▦ column chooser opens", await chooser.locator("div").first().isVisible());
// DEF-440 was the PO on this very panel: *"its square, 1 column in 1 row and
// arrows; in your UI it is disturbed"*. r10 draws each row as
// `[x] Label ......... [up][dn]`, ONCE, on one line.
const chooserRows = await chooser.locator("label").evaluateAll((els) =>
  els.map((el) => ({
    text: (el.textContent ?? "").trim().slice(0, 18),
    dir: getComputedStyle(el).flexDirection,
    h: Math.round(el.getBoundingClientRect().height),
  })),
);
check(
  "and every row of it is ONE line — checkbox BESIDE its label, not above it (DEF-440)",
  chooserRows.length > 0 && chooserRows.every((r) => r.dir === "row" && r.h <= 28),
  JSON.stringify(chooserRows.filter((r) => r.dir !== "row" || r.h > 28).slice(0, 4)),
);
check("and UNIT is one of the columns it offers", /(^|\n)\s*Unit\s*($|\n)/m.test(chooserText), JSON.stringify(chooserText.split("\n").slice(0, 14)));
await page.screenshot({ path: `${SHOT}/units-${TAG}-columns.png` });
await chooser.locator("summary").click();

// ── 11 · The + Filter panel is not a wall of 1,247 checkboxes ─────────────
const fpanel = page.locator(".table-toolbar details").first();
await fpanel.locator("summary").click();
await page.waitForTimeout(250);
const boxes = await fpanel.locator('input[type="checkbox"]').count();
check("the + Filter panel offers a workable number of boxes (B14 rule 9 / BR-SHL-033)", boxes > 0 && boxes <= 12, `${boxes} checkboxes`);
const panelText = await fpanel.locator("div").first().innerText();
const legends = await fpanel.locator("legend").allInnerTexts();
const emptyGroups = [];
for (const name of legends) {
  const group = fpanel.locator("fieldset", { has: fpanel.page().locator(`legend:text-is("${name}")`) });
  void group;
}
check(
  "every group in the panel offers at least one option (no legend over nothing)",
  (await fpanel.locator("fieldset").evaluateAll((sets) =>
    sets.filter((el) => el.querySelectorAll('input[type="checkbox"]').length === 0).map((el) => el.querySelector("legend")?.textContent ?? "?"),
  )).length === 0,
  JSON.stringify(await fpanel.locator("fieldset").evaluateAll((sets) =>
    sets.filter((el) => el.querySelectorAll('input[type="checkbox"]').length === 0).map((el) => el.querySelector("legend")?.textContent ?? "?"),
  )),
);
const optionRows = await fpanel.locator("label").evaluateAll((els) =>
  els.map((el) => ({
    text: (el.textContent ?? "").trim().slice(0, 18),
    dir: getComputedStyle(el).flexDirection,
    h: Math.round(el.getBoundingClientRect().height),
  })),
);
check(
  "every option in the panel is `\u2610 Label` on one line, as r10 draws it",
  optionRows.length > 0 && optionRows.every((r) => r.dir === "row" && r.h <= 28),
  JSON.stringify(optionRows.filter((r) => r.dir !== "row" || r.h > 28).slice(0, 4)),
);
check(
  "the Service group offers the tenant's ENABLED services and not the disabled one",
  panelText.includes("Electric") && panelText.includes("Water") && panelText.includes("Sewer") && !panelText.includes("Thermal"),
  JSON.stringify(legends) + " · " + JSON.stringify(panelText.split("\n").filter((l) => /Electric|Water|Sewer|Thermal/.test(l))),
);
await page.screenshot({ path: `${SHOT}/units-${TAG}-filterpanel.png` });
await fpanel.locator("summary").click();

// ── 12 · A scoped premise is a REMOVABLE CHIP (B14 rule 12) ───────────────
await page.goto(`${BASE}/${TENANT}/premises/units?sort=unit_no&dir=asc&f.premises_id=p-P-11024`, { waitUntil: "networkidle" });
await page.locator("tbody tr").first().waitFor({ state: "visible", timeout: 15000 });
await page.waitForTimeout(400);
const toolbarText = await page.locator(".table-toolbar").innerText();
check(
  "a premise-scoped units list SAYS which premise, on screen",
  toolbarText.includes("500 Main Plaza"),
  JSON.stringify(toolbarText.replace(/\n/g, " | ").slice(0, 160)),
);
const removeChip = page.getByRole("button", { name: /Remove .*Premise|Premise/i }).first();
const chipRemover = page.locator('.table-toolbar button[aria-label^="Remove"]');
check("and the scope can be dropped from the toolbar", (await chipRemover.count()) > 0, `${await chipRemover.count()} chip ✕ button(s)`);

// the scoped toolbar must ALSO be one row, and must not contradict itself
const tb2 = page.locator(".table-toolbar").first();
const tb2Box = await tb2.boundingBox();
// A CHIP IS CONTENT, and r10's own `.fbar` is `flex-wrap: wrap` — so a long
// chip may take a second band and that is the drawing, not drift. What must
// never come back is the THIRD band the premises grid forced (156px, measured).
check(
  "the scoped toolbar grows by at most one band as the chip wraps (r10 `.fbar` wraps too)",
  (tb2Box?.height ?? 999) <= 92,
  `${Math.round(tb2Box?.height ?? -1)}px — was 156px before this lane, with no chip on screen at all`,
);
const stray = page.locator("#f\\.premises_id");
const strayValue = (await stray.count()) > 0 ? await stray.inputValue() : null;
check(
  "the picker does not sit beside the chip still reading its placeholder",
  (await stray.count()) === 0,
  strayValue === null ? "picker absent — the chip is the control" : `picker present, showing ${JSON.stringify(strayValue)} while f.premises_id is applied`,
);await page.screenshot({ path: `${SHOT}/units-${TAG}-scoped.png` });
if ((await chipRemover.count()) > 0) {
  await chipRemover.first().click();
  await page.waitForTimeout(600);
  check("clicking its ✕ drops `f.premises_id` from the URL", !page.url().includes("f.premises_id"), page.url());
}
await page.goto(`${BASE}/${TENANT}/premises/units`, { waitUntil: "networkidle" });
await page.locator("tbody tr").first().waitFor({ state: "visible", timeout: 15000 });

await page.screenshot({ path: `${SHOT}/units-${TAG}-full.png`, fullPage: false });
await page.locator(".met-page, main").first().screenshot({ path: `${SHOT}/units-${TAG}-page.png` }).catch(() => {});

const failed = checks.filter((c) => !c.pass);
console.log(`\n${checks.length - failed.length}/${checks.length} checks passed`);
await browser.close();
process.exit(failed.length === 0 ? 0 : 1);
