// ── Trace ──────────────────────────────────────────────
// Defects: DEF-CUS-5480 (step 4's grid clipped after six rows and took the
//          wizard footer with it) · DEF-CUS-5481 (the work-order cell was
//          plain text; the install date drew its own label on every row)
// Process: 12-governance/22-product-maintenance-process.md §0 REPRODUCE, §4
//          PROVE IT AGAINST THE REPRODUCTION
// Rules:   hard-won law 6 (no gate in this repo reads rendered output) ·
//          law 7 (a check must distinguish pass from fail to a READER) ·
//          B14 rule 42 (a screen is judged as it renders)
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS EXISTS, AND WHY A UNIT TEST COULD NOT DO IT
// ══════════════════════════════════════════════════════════════════════════
//
// `DEF-CUS-5480` was a LAYOUT fault and every check in this repository passed
// over it. All fourteen rows were in the DOM, so counting cells said fourteen
// either way; the test environment does no layout, so every element there is
// zero by zero; and no gate reads rendered output. It was found by a person
// looking at the screen.
//
// **THE MEASUREMENT THAT NAMES IT IS ONE LINE:
// `document.documentElement.scrollHeight` against `clientHeight`.**
// On the broken screen those read **1,782 and 1,000** — the window carried a
// second scrollbar that scrolled 782px into empty grey, taking the app shell,
// the panel border and the Back/Continue footer with it. Every other long
// screen in the product reads them EQUAL; only this one did not, because a
// `labelHidden` control's `sr-only` label is `position: absolute` and, with no
// positioned ancestor, escapes `main.view`'s clip and enlarges the DOCUMENT.
//
// ⚠ **THIS WALK ASSERTS REACHABILITY, NOT VISIBILITY, AND THE DIFFERENCE IS
// THE PRODUCT'S (law 7 — know what would make this pass wrongly).** The screen
// legitimately holds more grid than a 1,000px window: the blueprint (p089)
// draws the grid running its full length with the footer below it, and no
// internal scroll region. So the pass mark is that the last row and the footer
// are REACHED by scrolling the screen's own scroller, and that the DOCUMENT
// does not scroll at all. A walk that only screenshotted the top would pass on
// the broken screen; a walk that demanded row 14 be visible at 1,000px would
// fail on the correct one.
//
// RUN:  node 10-scripts/def_cus_5480_step4_grid_walkthrough.mjs
//       BASE=http://127.0.0.1:8098 OUT=/tmp/def5480 UNITS=6
const { mkdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8098";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/def5480";
const UNITS = Number(process.env.UNITS ?? 6);
mkdirSync(OUT, { recursive: true });

const say = (...a) => console.log(...a);
const failures = [];
const check = (ok, sentence) => {
  say(`  ${ok ? "PASS" : "FAIL"}  ${sentence}`);
  if (!ok) failures.push(sentence);
};

const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium" });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await ctx.newPage();

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

// ⚠ **THE RADIOS ARE VISUALLY HIDDEN AND ZERO-SIZED**, so they can never be
// "in the viewport" and neither `check()` nor `scrollIntoViewIfNeeded()` will
// ever succeed. The control a person clicks is the label around it; dispatching
// the click on the input is the same event React binds to.
const pick = async (name, value) => {
  const el = await page.$(`input[name="${name}"][value="${value}"]`);
  if (el !== null) await el.evaluate((n) => n.click());
};
const forward = async () => {
  const buttons = await page.$$('[data-wizard="actions"] button');
  await buttons[buttons.length - 1].click();
  await page.waitForTimeout(1300);
};

await page.goto(`${BASE}/${TENANT}/connections/new`, { waitUntil: "networkidle" });
await page.waitForTimeout(1200);

// ── steps 1-3, to get a build with fourteen grid rows ────────────────────
const STAMP = new Date().toISOString().replace(/[^0-9]/g, "").slice(0, 14);
await page.selectOption("#nc_owner_kind", "builder_developer").catch(() => {});
await page.fill("#nc_owner_name", "Grid Walk Developments LLC");
await page.selectOption("#nc_owner_subcategory", "permanent").catch(() => {});
await pick("nc_party_kind", "company");
await page.waitForTimeout(400);
for (const s of ["#nc_tax_id", "#nc_owner_tax_id"]) {
  if (await page.$(s)) await page.fill(s, `TX-${STAMP.slice(8)}`).catch(() => {});
}
await page.fill("#nc_prefix", "Apt").catch(() => {});
await pick("nc_scope", "new_premise");
await pick("nc_mode", "our_crew");
await forward();

await page.fill("#nc_address", `${STAMP.slice(8)} Grid Walk Drive`).catch(() => {});
for (const [s, v] of [["#nc_city", "Austin"], ["#nc_postal_code", "78704"], ["#nc_zip", "78704"],
                      ["#nc_premises_name", "Grid Walk Court"], ["#nc_name", "Grid Walk Court"]]) {
  if (await page.$(s)) await page.fill(s, v).catch(() => {});
}
if (await page.$("#nc_state")) await page.fill("#nc_state", "TX").catch(() => {});
const ptypes = await page.$$eval("#nc_premise_type option", (ns) =>
  ns.map((o) => o.value).filter(Boolean)).catch(() => []);
if (ptypes.length) await page.selectOption("#nc_premise_type", ptypes[0]);
await page.waitForSelector("#services_available-add", { timeout: 15000 }).catch(() => {});
const offered = await page.$$eval("#services_available-add option", (ns) =>
  ns.map((o) => o.value).filter(Boolean)).catch(() => []);
for (const code of offered) {
  await page.selectOption("#services_available-add", code).catch(() => {});
  await page.waitForTimeout(250);
}
await forward();

await page.fill("#nc_from", "1").catch(() => {});
await page.fill("#nc_to", String(UNITS)).catch(() => {});
await page.waitForTimeout(600);
await forward();
await page.waitForTimeout(1500);

say(`\n══ STEP 4 · ${UNITS} units x ${offered.length} services ══`);

// ══════════════════════════════════════════════════════════════════════════
// DEF-CUS-5480 · THE DOCUMENT MUST NOT SCROLL
// ══════════════════════════════════════════════════════════════════════════
const doc = await page.evaluate(() => ({
  scrollH: document.documentElement.scrollHeight,
  clientH: document.documentElement.clientHeight,
  rows: document.querySelectorAll("[data-unit-service-grid] tbody tr").length,
}));
say(`  document ${doc.scrollH}px in a ${doc.clientH}px window · ${doc.rows} rows`);
check(
  doc.scrollH === doc.clientH,
  `the window carries no phantom scroll region (document ${doc.scrollH} = viewport ${doc.clientH})`,
);
check(doc.rows === UNITS * offered.length + offered.length, `the grid holds ${doc.rows} rows`);

await page.setViewportSize({ width: 1280, height: 1000 });
await page.waitForTimeout(400);
await page.screenshot({ path: `${OUT}/step4-1280.png`, fullPage: true });
await page.setViewportSize({ width: 1440, height: 1000 });
await page.waitForTimeout(400);
await page.screenshot({ path: `${OUT}/step4-1440.png`, fullPage: true });

// ⚠ **THE PANEL AND THE FOOTER ARE REACHED, NOT MERELY PRESENT.** Scroll the
// screen's own scroller to the bottom, the way a clerk's wheel does, and demand
// a non-zero box INSIDE the window for the last row and for Continue.
await page.evaluate(() => {
  const v = document.querySelector("main.view");
  if (v !== null) v.scrollTop = v.scrollHeight;
});
await page.waitForTimeout(500);
const bottom = await page.evaluate(() => {
  const rows = document.querySelectorAll("[data-unit-service-grid] tbody tr");
  const last = rows[rows.length - 1];
  const panel = last?.closest("[data-panel]") ?? null;
  const actions = document.querySelector('[data-wizard="actions"]');
  const buttons = actions === null ? [] : Array.from(actions.querySelectorAll("button"));
  const forward = buttons[buttons.length - 1] ?? null;
  const inWindow = (el) => {
    if (el === null) return false;
    const r = el.getBoundingClientRect();
    return r.height > 0 && r.width > 0 && r.top >= 0 && r.bottom <= window.innerHeight;
  };
  return {
    lastRowLabel: last?.querySelector("td")?.textContent ?? "",
    lastRowInWindow: inWindow(last),
    panelBottomInWindow: panel === null
      ? false
      : panel.getBoundingClientRect().bottom <= window.innerHeight,
    forwardLabel: forward?.textContent?.trim() ?? "",
    forwardInWindow: inWindow(forward),
    forwardDisabled: forward?.disabled ?? true,
  };
});
check(bottom.lastRowInWindow, `the last row (${bottom.lastRowLabel}) is reached by scrolling`);
check(bottom.panelBottomInWindow, "the panel's bottom border is reached, so the table ends visibly");
check(bottom.forwardInWindow, `the wizard footer is reached — "${bottom.forwardLabel}" has a box`);
check(!bottom.forwardDisabled, `"${bottom.forwardLabel}" is pressable`);
await page.screenshot({ path: `${OUT}/step4-scrolled-1440.png` });

// ══════════════════════════════════════════════════════════════════════════
// DEF-CUS-5481 · THE ROW IS CONTROLS, AND THEY LINE UP
// ══════════════════════════════════════════════════════════════════════════
await page.evaluate(() => {
  const v = document.querySelector("main.view");
  if (v !== null) v.scrollTop = 0;
});
await page.waitForTimeout(300);
const cells = await page.evaluate(() => {
  const rows = Array.from(document.querySelectorAll("[data-unit-service-grid] tbody tr"));
  const orders = document.querySelectorAll('[data-unit-service-grid] select[id^="nc_workorder_"]');
  const first = orders[0] ?? null;
  // A visible label is one with a box; `sr-only` collapses to 1x1 and is not.
  const drawnLabels = Array.from(
    document.querySelectorAll("[data-unit-service-grid] tbody label"),
  ).filter((l) => l.textContent?.trim() === "Install date" && l.getBoundingClientRect().height > 2);
  // Every control on ONE row shares a top edge, to the nearest pixel.
  const controlTops = (row) =>
    Array.from(row.querySelectorAll("select, input[type=date]"))
      .map((c) => Math.round(c.getBoundingClientRect().top));
  const misaligned = rows.filter((row) => new Set(controlTops(row)).size > 1).length;
  return {
    orderSelects: orders.length,
    orderOptions: first === null ? 0 : first.options.length,
    orderSelected: first?.selectedOptions[0]?.textContent ?? "",
    drawnInstallLabels: drawnLabels.length,
    misalignedRows: misaligned,
    rows: rows.length,
  };
});
check(cells.orderSelects === cells.rows, `every work-order cell is a control (${cells.orderSelects}/${cells.rows})`);
check(cells.orderOptions > 1, `the clerk can choose a different job (${cells.orderOptions} options)`);
check(cells.orderSelected !== "", `the row opens on a default — "${cells.orderSelected}"`);
check(cells.drawnInstallLabels === 0, `no row draws its own "Install date" label (${cells.drawnInstallLabels} drawn)`);
check(cells.misalignedRows === 0, `every row's controls share one top edge (${cells.misalignedRows} misaligned)`);

// ══════════════════════════════════════════════════════════════════════════
// THE NEIGHBOURS — a fix that breaks an adjacent step is worse than the defect
// ══════════════════════════════════════════════════════════════════════════
await forward();
const step5 = await page.evaluate(() => ({
  heading: document.querySelector("h1,h2")?.textContent?.trim() ?? "",
  doc: document.documentElement.scrollHeight === document.documentElement.clientHeight,
}));
check(step5.heading !== "", `step 5 still opens — "${step5.heading}"`);
check(step5.doc, "step 5 carries no phantom scroll region either");
await page.screenshot({ path: `${OUT}/step5-1440.png`, fullPage: true });

say(`\n══ ${failures.length === 0 ? "ALL CHECKS PASSED" : `${failures.length} FAILED`} ══`);
failures.forEach((f) => say("  · " + f));
say(`screens: ${OUT}`);
await browser.close();
process.exit(failures.length === 0 ? 0 : 1);
