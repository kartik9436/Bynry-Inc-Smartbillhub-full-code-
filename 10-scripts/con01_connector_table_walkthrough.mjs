// ── Trace ──────────────────────────────────────────────
// Change:  PO rulings 2026-09-17 — *"we are overriding the deciion and
//          converting it form Grid -> Table - table only"*, the four-action
//          cell (*"Action im looking for - Connect, View, Edit, Keys- based on
//          this status will chnage"*, ratified over the full matrix as *"this
//          is good - please add it"*) and the ten columns (*"Im good with
//          these columes - please implment it"*). Recorded in
//          `12-governance/02-decision-log.md`, 2026-09-17.
// Screens: S8 · CON-01, at `/:tenant/settings/integrations`.
// Rules:   CLAUDE.md hard-won law 6 (no gate in this repo reads rendered
//          output — diff the running app) · law 7 habits 2 and 3 (what would
//          make this pass wrongly; the OUTPUT must distinguish pass from fail
//          to a READER) · B14 rule 15 · BR-SHL-025 · the staff widths of the
//          UI skill — 1280 and 1440, and nothing narrower.
// ───────────────────────────────────────────────────────
/**
 * Look at the connector TABLE the way a clerk does, at both staff widths.
 *
 *     BASE=http://127.0.0.1:5200 node 10-scripts/con01_connector_table_walkthrough.mjs
 *
 * ⚠ **IT ASSERTS WHAT THE STACK SERVES BEFORE IT BELIEVES ANY SCREENSHOT.**
 * That clause is paid for: on 2026-09-16 a front end was started on a port
 * another lane already held, so it never bound, the browser was quietly served
 * by the OLDER stack, and its retired connectors were reported to the PO as a
 * product fault. A walk against the wrong bundle is not a weaker proof — it is
 * a proof of a different product. So this reads the PROVIDER COUNT off the API
 * and the JS BUNDLE HASH out of the served HTML, and prints both, before it
 * looks at a single pixel.
 *
 * ⚠ **WHAT WOULD MAKE THIS WALK PASS WRONGLY, AND WHAT IS DONE ABOUT IT:**
 *
 *  * **A screenshot proves a screen EXISTS, never that it is RIGHT.** So
 *    nothing here is scored by looking at an image: every line below is a
 *    measurement read out of the live DOM or out of `getComputedStyle`, and
 *    the images are for a person to look at afterwards.
 *  * **`document.body.scrollWidth <= innerWidth` is the WRONG test for
 *    horizontal scroll** on a page whose table may scroll INSIDE its own
 *    container — it passes while the table is clipped. Both are measured and
 *    both are printed, separately, because they are different facts.
 *  * **A `Why` column is empty on a healthy tenant**, so *the column rendered*
 *    and *the column can never render* look identical. The walk FINDS a row in
 *    `Not working` and reads the sentence out of that row's cell — and says so
 *    when the tenant has none, rather than scoring a silent pass.
 *  * **Counting four buttons per row proves nothing** if they are the same four
 *    everywhere. The enabled/greyed SPLIT is read per row and tallied by state,
 *    so a cell that greyed everything or greyed nothing is visible in the
 *    output as a number a reader can disagree with.
 *  * ⚠ **`input[type="search"]` MATCHES TWO BOXES ON THIS SCREEN AND THE FIRST
 *    ONE IS THE SHELL'S.** The app frame carries a universal search
 *    (placeholder *Search*, hitting `/api/{tenant}/search?q=`) and the table
 *    carries its own (*Search services…*). The first draft of this walk typed
 *    into the shell's and reported **"28 rows → 28 — the search does not
 *    filter"** about a screen whose search works perfectly. That is law 7's
 *    *looking at the wrong thing*, and it nearly became a filed defect against
 *    working code. **Every list control here is scoped to `.data-table-frame`.**
 */
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright-core");
const fs = await import("node:fs/promises");

const BASE = process.env.BASE ?? "http://127.0.0.1:5200";
const TENANT = process.env.TENANT ?? "brazosbend";
const OUT = process.env.OUT ?? "/tmp/con01";
const EXE =
  process.env.CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
await fs.mkdir(OUT, { recursive: true });

const browser = await chromium.launch({ executablePath: EXE });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 950 } });
const page = await ctx.newPage();

// ── 0 · WHAT IS THIS STACK, ACTUALLY ──────────────────────────────────────
const html = await (await fetch(`${BASE}/${TENANT}/settings/integrations`)).text();
const bundle = (/assets\/(index-[^"]+\.js)/.exec(html) ?? [])[1] ?? "UNKNOWN";
console.log(`STACK: ${BASE} · bundle ${bundle}`);

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
// The sign-in form's own ids — the same two `def_int_5513_connect_door_walkthrough.mjs`
// uses, so both walks break together if the form is rebuilt.
await page.fill("#signin-email", "dana@brazosbendutilities.com");
await page.fill("#signin-password", "S3cure!passw0rd");
await page.click('button[type="submit"]');
// ⚠ **WAIT FOR THE DESTINATION, NOT FOR `networkidle`.** The click starts a
// navigation, so `waitForLoadState` can resolve against the page being LEFT —
// the session cookie is not set yet, the probe below reads 401, and the walk
// reports "not 28 connectors" about a product that is fine. It cost one run.
await page.waitForURL(/\/dashboard/, { timeout: 20000 });

const served = await page.evaluate(async (tenant) => {
  const r = await fetch(`/api/${tenant}/integrations`, { credentials: "include" });
  if (!r.ok) return `HTTP ${r.status}`;
  const body = await r.json();
  return (body.providers ?? []).length;
}, TENANT);
console.log(`STACK: the API serves ${served} connectors`);
if (served !== 28) {
  console.log(
    `  ⚠ NOT 28. Every judgment below is about whatever this stack is, not about the product.`,
  );
}

// ── 1 · THE TABLE, AT BOTH STAFF WIDTHS ───────────────────────────────────
/** Read the whole screen as measurements, at one width. */
async function measure(width) {
  await page.setViewportSize({ width, height: 950 });
  await page.goto(`${BASE}/${TENANT}/settings/integrations`, { waitUntil: "networkidle" });
  await page.waitForSelector("table", { timeout: 15000 });
  return page.evaluate(() => {
    const table = document.querySelector("table");
    const headers = [...table.querySelectorAll("thead th")].map((th) =>
      (th.textContent ?? "").trim(),
    );
    const rows = [...table.querySelectorAll("tbody tr")];
    const scroller = table.closest("div");
    const readRow = (tr) => {
      const cellText = (name) =>
        (tr.querySelector(`[data-cell="${name}"]`)?.textContent ?? "").trim();
      const cell = tr.querySelector("[data-row-actions]");
      const acts = cell === null ? [] : [...cell.querySelectorAll("button, a")];
      return {
        key: tr.querySelector("[data-provider]")?.getAttribute("data-provider") ?? "?",
        name: (tr.querySelector("[data-connector-link]")?.textContent ?? "").trim(),
        state: (tr.querySelector('[data-cell="state"]')?.textContent ?? "").trim(),
        apis: cellText("apis"),
        environment: cellText("environment"),
        where: cellText("where"),
        lastRun: cellText("lastRun"),
        why: cellText("why"),
        height: Math.round(tr.getBoundingClientRect().height),
        actions: acts.map((a) => ({
          label: a.getAttribute("aria-label"),
          live: a.tagName === "A",
          title: a.getAttribute("title"),
        })),
      };
    };
    return {
      headers,
      rowCount: rows.length,
      rows: rows.map(readRow),
      // TWO different facts, printed apart — see the header.
      pageScrolls: document.body.scrollWidth > window.innerWidth,
      tableClipped: scroller === null ? null : scroller.scrollWidth > scroller.clientWidth + 1,
      tableWidth: Math.round(table.getBoundingClientRect().width),
      // ⚠ **IS THE *ACTIONS* COLUMN ACTUALLY ON SCREEN?** *The table scrolls
      // inside its frame* is the sanctioned behaviour and it is NOT the same
      // question as *can a clerk see the controls without scrolling*. The
      // actions cell is the last column and the point of the whole ruling, so
      // it is measured by NAME against the frame's right edge rather than left
      // to a reader to infer from a table width. `DEF-INT-5577`.
      actionsInFrame: (() => {
        const th = [...table.querySelectorAll("thead th")].at(-1);
        const frame = table.closest("div");
        if (th === undefined || frame === null) return null;
        return Math.round(th.getBoundingClientRect().right) <= Math.round(frame.getBoundingClientRect().right) + 1;
      })(),
      headerWraps: [...table.querySelectorAll("thead th")]
        // ⚠ 44, NOT 34. A header row measures 35px in this theme with its own
        // padding, so a `> 34` threshold reported ALL TEN as wrapping on a
        // screen where none does — a check whose output could not distinguish
        // pass from fail (law 7 habit 3). One line is 35; two would be ~54.
        .filter((th) => th.getBoundingClientRect().height > 44)
        .map((th) => (th.textContent ?? "").trim()),
      footnote: (
        document.querySelector("section > p:last-of-type")?.textContent ?? ""
      ).trim(),
    };
  });
}

for (const width of [1280, 1440]) {
  const m = await measure(width);
  await page.screenshot({ path: `${OUT}/con01-${width}.png`, fullPage: false });
  console.log(`\n── ${width}px ──────────────────────────────────────────────`);
  // ⚠ **PRINT THE COLUMNS THAT ARE ACTUALLY THERE, EVERY RUN.** The `▦`
  // chooser's set is a PER-USER SERVER-SIDE PREFERENCE (`BR-SHL-027`), so a
  // walk that hid three columns once measures the seven-column table on every
  // later run and reports a table that fits. That happened while this file was
  // being written: 1,346px became 1,120px and *"ACTIONS visible: yes"* over a
  // screen nobody had changed. The count is the reader's protection.
  console.log(`  columns   : ${m.headers.length} — ${m.headers.join(" · ")}`);
  console.log(`  rows      : ${m.rowCount}   table ${m.tableWidth}px`);
  console.log(`  page scrolls sideways : ${m.pageScrolls ? "YES — a fault" : "no"}`);
  console.log(
    `  table scrolls inside its frame: ${m.tableClipped ? "yes (sanctioned — the PAGE must not)" : "no"}`,
  );
  console.log(
    `  ACTIONS column visible without scrolling: ${m.actionsInFrame ? "yes" : "NO — DEF-INT-5577"}`,
  );
  console.log(
    `  header wraps to 2 lines: ${m.headerWraps.length === 0 ? "none" : m.headerWraps.join(", ")}`,
  );
  // ⚠ 64, NOT 56. A ONE-LINE row measures 59px in this theme once its own
  // padding is counted, so a `> 56` threshold listed all 28 one-line rows as
  // "taller than one line" — an output that cannot distinguish pass from fail
  // to a reader, which is the fault law 7 habit 3 names. Two lines is ~80.
  const tall = m.rows.filter((r) => r.height > 64);
  console.log(
    `  rows taller than one line: ${tall.length === 0 ? "none" : tall.map((r) => `${r.key} ${r.height}px`).join(", ")}`,
  );
  console.log(`  footnote  : ${m.footnote}`);

  if (width === 1440) {
    // ── Neptune, the card that started all this ───────────────────────────
    const nep = m.rows.find((r) => /neptune/i.test(r.key) || /neptune/i.test(r.name));
    console.log(`\n  NEPTUNE'S ROW:`);
    if (nep === undefined) {
      console.log(`    ⚠ no Neptune row on this stack — the walk cannot judge it.`);
    } else {
      console.log(
        `    ${nep.name} | ${nep.state} | APIs ${nep.apis} | ${nep.environment} | ${nep.where} | last run ${nep.lastRun || "(never)"} | why ${nep.why || "(empty)"}`,
      );
      console.log(`    row height ${nep.height}px`);
      console.log(
        `    actions: ${nep.actions.map((a) => `${a.label}${a.live ? "" : ` (greyed: ${a.title})`}`).join(" · ")}`,
      );
    }

    // ── the actions matrix, tallied from the LIVE screen ──────────────────
    console.log(`\n  THE FOUR ACTIONS, PER ROW — the ratified matrix, measured:`);
    const bad = [];
    for (const r of m.rows) {
      const labels = r.actions.map((a) => a.label).join(",");
      if (labels !== "Connect,View,Edit,Keys") bad.push(`${r.key}: [${labels}]`);
      const silent = r.actions.filter((a) => !a.live && !a.title);
      if (silent.length > 0) bad.push(`${r.key}: greyed with no reason`);
    }
    const byState = new Map();
    for (const r of m.rows) {
      const live = r.actions.filter((a) => a.live).map((a) => a.label).join("/") || "(none)";
      const key = `${r.state} → live: ${live}`;
      byState.set(key, (byState.get(key) ?? 0) + 1);
    }
    for (const [k, n] of [...byState.entries()].sort()) console.log(`    ${n.toString().padStart(3)} × ${k}`);
    console.log(
      `    four-icons-in-order on every row: ${bad.length === 0 ? "YES" : `NO — ${bad.join("; ")}`}`,
    );

    // ── the Why column: found, not inferred (law 7's third shape) ─────────
    const failing = m.rows.filter((r) => /not working/i.test(r.state));
    console.log(`\n  THE *WHY* COLUMN:`);
    if (failing.length === 0) {
      console.log(
        `    ⚠ NO connector is in *Not working* on this tenant, so this walk CANNOT`,
      );
      console.log(
        `      show the column doing its job. That is an unproved column, not a passing one.`,
      );
    } else {
      for (const r of failing) {
        console.log(`    ${r.key}: "${r.why || "(EMPTY — the column is not reading its field)"}"`);
      }
    }
    const healthyWithWhy = m.rows.filter((r) => !/not working/i.test(r.state) && r.why !== "");
    console.log(
      `    healthy rows carrying text in Why: ${healthyWithWhy.length} (must be 0 — the column is scanned for red)`,
    );

    // ── the three connection-backed columns on an unconnected row ────────
    const none = m.rows.filter((r) => r.state === "Not set up" || r.actions.every((a) => !a.live));
    const fabricated = none.filter(
      (r) => r.environment !== "" || r.where !== "" || r.why !== "",
    );
    console.log(
      `\n  rows with no connection: ${none.length}; of those, any drawing a value in Environment/Where/Why: ${fabricated.length} (must be 0)`,
    );
  }
}

// ── 2 · THE TOOLBAR STILL WORKS ───────────────────────────────────────────
await page.setViewportSize({ width: 1440, height: 950 });
await page.goto(`${BASE}/${TENANT}/settings/integrations`, { waitUntil: "networkidle" });
await page.waitForSelector("table");

const before = await page.$$eval("tbody tr", (r) => r.length);
const searchBox = await page.$('.data-table-frame input[type="search"]');
await searchBox.click();
await page.keyboard.type("neptune", { delay: 60 });
await page.waitForTimeout(1200);
const afterSearch = await page.$$eval("tbody tr", (r) => r.length);
const searchFootnote = await page.evaluate(
  () => (document.querySelector("section > p:last-of-type")?.textContent ?? "").trim(),
);
await searchBox.fill("");
await page.waitForTimeout(1200);

// ⚠ SCOPED TO THE CHOOSER'S OWN `<details>`, not to the toolbar's. There are
// TWO `<details>` panels in this toolbar — `+ Filter ▾` and `▦` — and a query
// across both counted 21 "columns" (10 real + 11 filter options) and read like
// a table with twenty-one columns. Its own panel is the element the summary
// belongs to.
const chooser = await page.$('.data-table-frame [aria-label="Show or hide columns"]');
let chooserWorks = "not found";
if (chooser !== null) {
  await chooser.click();
  const items = await chooser.evaluate((el) =>
    [...(el.closest("details") ?? el.parentElement).querySelectorAll("input[type=checkbox]")].map(
      (i) => ({ label: (i.closest("label")?.textContent ?? "").trim(), disabled: i.disabled }),
    ),
  );
  chooserWorks =
    `${items.length} columns, ${items.filter((i) => i.disabled).length} locked — ` +
    `hideable: ${items.filter((i) => !i.disabled).map((i) => i.label).join(", ") || "(none)"}`;
  // ⚠ `<details>` DOES NOT CLOSE ON Escape. Leaving it open makes the toolbar
  // overlay the header row, and the sort click below was intercepted by it for
  // two runs — a walk failing on its own leftovers rather than on the product.
  await page.evaluate(() =>
    document.querySelectorAll("details[open]").forEach((d) => d.removeAttribute("open")),
  );
}

const filterPanel = await page.$(".data-table-frame details summary");
let filterWorks = "not found";
if (filterPanel !== null) {
  await filterPanel.click();
  filterWorks = ((await page.textContent(".data-table-frame details")) ?? "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 140);
  await page.evaluate(() =>
    document.querySelectorAll("details[open]").forEach((d) => d.removeAttribute("open")),
  );
}

console.log(`\n── THE TOOLBAR ────────────────────────────────────────────`);
console.log(`  search "neptune": ${before} rows → ${afterSearch}`);
console.log(`                   footnote said: ${searchFootnote}`);
console.log(`  ▦ columns      : ${chooserWorks}`);
console.log(`  + Filter       : ${filterWorks}`);

// ── 3 · SORT BY LAST RUN — the column a card could not give you ───────────
const sortHeader = await page.$('.data-table-frame thead th:has-text("Last run") button');
let sortResult = "no sortable Last run header";
if (sortHeader !== null) {
  await sortHeader.click();
  await page.waitForTimeout(400);
  const first = await page.$$eval("tbody tr", (rows) =>
    rows.slice(0, 3).map((r) => (r.querySelector('[data-cell="lastRun"]')?.textContent ?? "").trim()),
  );
  sortResult = `top three after one press: ${first.map((f) => f || "(never)").join(" | ")}`;
}
console.log(`  Last run sort  : ${sortResult}`);

console.log(`\nscreenshots in ${OUT}`);
await browser.close();
