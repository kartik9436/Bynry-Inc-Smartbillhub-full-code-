// ── Trace ──────────────────────────────────────────────
// Change:   `BR-CUS-1094` (PO 2026-09-23) — the **Units** tab on a master
//           account, and what will be billed to it. PO verbatim: *"show all
//           units with its status what wil be billed to master account - can
//           we do that?"*
// Rules:    CLAUDE.md hard-won law 6 (diff the running app against the
//           drawing — no gate in this repo reads rendered output) · law 2
//           (built is not wired, and its mirror: a live screen behind a dead
//           control) · B14 rule 31 (no database id is ever a visible value,
//           and an ADDRESS BAR is a visible field) · rule 12 (the toolbar's
//           grammar) · rule 16 (a pagination footer on every list) ·
//           BR-CUS-1094 · BR-CUS-170 · BR-CUS-1040
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT THIS ASKS THAT NO SUITE CAN
// ══════════════════════════════════════════════════════════════════════════
// Five things, and every one is invisible to `tsc`, to the 16 unit cases and
// to every gate in this repository:
//
//   1. **Does the tab RENDER**, or does a green suite sit over a page that
//      throws on mount? `renderToStaticMarkup` never runs an effect, and this
//      tab's whole body is a `useQuery` that only runs in a browser.
//   2. **Does the DOOR exist?** `accountTabIds` returning `units` is a
//      constant; a clerk needs a tab they can click. Hard-won law 2's mirror
//      is a live screen nothing points at, and this clicks the word.
//   3. **Does the SERVER answer?** The 16 unit cases seed the query cache, so
//      they prove the render and say nothing about `GET /accounts/{id}/units`.
//      This is the only thing that runs the real endpoint.
//   4. **Is a `Billed to` value printed on EVERY row?** `BR-CUS-1094` and the
//      blueprint agree there is never a dash in that column — *"a dash on
//      that row reads as `nothing is billed`, which is the opposite of
//      true"*. A blank cell is the defect this screen exists to prevent.
//   5. **Is a uuid on screen or in the address bar?** B14 rule 31.
//
// ⚠ **IT BOOTS NOTHING, ON PURPOSE.** `11-smoke-stack.sh` boots a stack and
// TEARS IT DOWN on exit, which is right for a smoke run and wrong for looking
// at a screen. Point it at an already-running SPA join:
//
//     cd 06-backend && python3 manage.py runserver 127.0.0.1:8211 --noreload &
//     cd 07-frontend && ./node_modules/.bin/vite build
//     PORT=8212 API_PROXY_TARGET=http://127.0.0.1:8211 node server.mjs &
//     PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers WEB=http://127.0.0.1:8212 \
//       node 10-scripts/br_cus_1094_master_units_walkthrough.mjs
//
// ⚠ **"NO MASTER ACCOUNT" IS A REAL RESULT AND NOT A CRASH.** The sample data
// may hold none; this says so and exits 0 with the reason named, because a
// walkthrough that cannot tell *the screen is broken* from *there is nothing
// to look at* is worse than none — it is believed (hard-won law 7).
import { mkdirSync, existsSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

// `playwright-core` is BORROWED from `07-frontend`, not imported: a bare
// specifier in an ESM module resolves from the MODULE's directory, never the
// CWD. `12-smoke-walkthrough.mjs` solved this first and this is its solution.
const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of [
        "chrome-linux64/chrome",
        "chrome-linux/chrome",
        "chrome-linux/headless_shell",
      ]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) {
          console.log(`chromium: pinned revision missing; using ${candidate}`);
          return candidate;
        }
      }
    }
  }
  throw new Error("no chromium found — and `playwright install` is forbidden here");
}

const WEB = process.env.WEB || "http://127.0.0.1:8212";
const TENANT = process.env.SMOKE_TENANT || "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT || "/tmp/claude-0/lane-maunits/shots";
mkdirSync(OUT, { recursive: true });

const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;
const findings = [];
function note(step, what) {
  findings.push(`[${step}] ${what}`);
  console.log(`  · ${step}: ${what}`);
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
page.on("pageerror", (e) => note("console", `PAGE ERROR: ${e.message}`));

// ⚠ **EVERY `/accounts/*/units` RESPONSE IS RECORDED**, because the screen can
// only draw what the server sent and a lane reading the screen alone cannot
// tell a missing column from a missing field.
const answers = [];
page.on("response", async (res) => {
  if (!/\/accounts\/[^/]+\/units(\?|$)/.test(res.url())) return;
  answers.push({ status: res.status(), body: await res.text().catch(() => "") });
});

try {
  console.log("step 1 · sign in");
  await page.goto(`${WEB}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(`**/${TENANT}/dashboard`, { timeout: 25000 });

  console.log("step 2 · find a master account on the register");
  await page.goto(`${WEB}/${TENANT}/accounts?f.kind=master`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `${OUT}/01-register-masters-1440.png`, fullPage: true });
  const masterRows = await page.locator("tbody tr").count();
  note("register", `${masterRows} master account row(s) in this tenant`);
  const firstDoor = await page.locator("tbody tr td a").first().getAttribute("href");
  if (!firstDoor) {
    note("register", "NO MASTER ACCOUNT IN THIS TENANT — nothing to walk, and that is a");
    note("register", "real result, not a failure. Seed one and re-run.");
    console.log("\n" + findings.join("\n"));
    await browser.close();
    process.exit(0);
  }
  note("register", `the first master's door = ${JSON.stringify(firstDoor)}`);

  console.log("step 3 · the account detail — is the Units tab a door a clerk can click?");
  await page.goto(`${WEB}${firstDoor}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `${OUT}/02-account-detail-1440.png`, fullPage: true });
  const tabs = await page.locator('[role="tab"]').allTextContents();
  note("S21", `tab strip = ${JSON.stringify(tabs)}`);
  const unitsTab = page.locator('[role="tab"]', { hasText: /^Units$/ }).first();
  if ((await unitsTab.count()) === 0) {
    note("S21", "DEAD DOOR: the Units tab is not in the rendered strip (hard-won law 2)");
  } else {
    note("S21", `Units is tab ${tabs.indexOf("Units") + 1} of ${tabs.length}`);
    // ⚠ **CLICKED, not navigated to by URL.** A tab that only opens when you
    // type its address is a screen with no door — law 2's mirror exactly.
    await unitsTab.click();
    await page.waitForTimeout(2500);
  }

  console.log("step 4 · the Units tab");
  await page.screenshot({ path: `${OUT}/03-units-tab-1440.png`, fullPage: true });
  note("units", `address bar = ${JSON.stringify(page.url().replace(WEB, ""))}`);
  if (UUID.test(page.url())) {
    note("units", "B14 RULE 31 BREACH: a uuid is in the ADDRESS BAR");
  }

  note("units", `${answers.length} call(s) to GET /accounts/{id}/units`);
  for (const answer of answers) {
    note("units", `server answered ${answer.status}`);
    if (answer.status !== 200) {
      note("units", `body = ${answer.body.slice(0, 300)}`);
      continue;
    }
    let parsed = null;
    try {
      parsed = JSON.parse(answer.body);
    } catch {
      note("units", "the body is not JSON");
      continue;
    }
    note("units", `count = ${parsed.count}, counts = ${JSON.stringify(parsed.counts)}`);
    const rows = parsed.results ?? [];
    // **Every row must name a payer.** There is no fourth value and there is
    // no blank — a row with neither would be the dash the blueprint forbids.
    const payers = rows.map((r) => r.payer);
    note("units", `payers served = ${JSON.stringify([...new Set(payers)])}`);
    const blank = rows.filter((r) => !r.payer);
    if (blank.length > 0) {
      note("units", `DEFECT: ${blank.length} row(s) name NO payer at all`);
    }
    // `BR-CUS-1040` — a payer, never a price.
    const priced = rows.filter((r) =>
      ["base_charge", "will_cost", "forecast", "estimated_amount"].some((k) => k in r),
    );
    if (priced.length > 0) {
      note("units", `DEFECT: ${priced.length} row(s) carry a PRICE (BR-CUS-1040)`);
    }
    // The two derived occupancies must agree, or one row says *vacant* in its
    // pill and *billed to the tenant* beside it.
    const disagree = rows.filter(
      (r) => r.metering_occupancy != null && r.metering_occupancy !== r.occupancy,
    );
    if (disagree.length > 0) {
      note("units", `DEFECT: ${disagree.length} row(s) disagree about occupancy`);
    }
  }

  console.log("step 5 · what a clerk can actually read on the rendered tab");
  const rendered = await page.locator("tbody tr").count();
  note("units", `${rendered} row(s) rendered`);
  if (rendered === 0) {
    note("units", "EMPTY STATE — the header row and the pager are not drawn, so");
    note("units", "no control check. This is not a finding about the controls.");
  } else {
    const headings = await page.locator("thead th").allTextContents();
    note("units", `columns = ${JSON.stringify(headings.map((h) => h.trim()))}`);
    // **The column this tab exists for, read off the RENDERED cells.** A
    // heading with empty cells under it is the defect; the count below is what
    // separates them.
    const billed = await page.locator("[data-billed-to]").count();
    note("units", `${billed} of ${rendered} row(s) print a Billed to value`);
    if (billed < rendered) {
      note("units", `DEFECT: ${rendered - billed} row(s) leave Billed to BLANK`);
    }
    for (const kind of ["tenant", "this-account", "nobody"]) {
      const n = await page.locator(`[data-billed-to="${kind}"]`).count();
      note("units", `  ${n} row(s) billed to ${kind}`);
    }
    // The vacancy sentence, drawn by the imported `OccupantCell`.
    const vacantCells = await page.locator('[data-occupant-state="vacant"]').count();
    note("units", `${vacantCells} vacant row(s) carry the owner-billing sentence`);
    const controls = {
      "search box (rule 12)": 'input[type="search"], .data-table-toolbar input',
      "+ Filter (rule 12)": '[data-filter-bar] summary, summary:has-text("Filter")',
      "sortable header (rule 13)": "th button, th [aria-sort]",
      "pagination footer (rule 16)": '.data-table-footer, [class*="pager"], .table-pager',
    };
    for (const [what, selector] of Object.entries(controls)) {
      const seen = await page.locator(selector).count();
      note("units", `${seen > 0 ? "present" : "MISSING"} — ${what}`);
    }
  }

  const body = (await page.textContent("body")) ?? "";
  if (UUID.test(body)) {
    note("units", "B14 RULE 31 BREACH: something uuid-shaped is on screen");
  }
  // A key the eleven catalogues do not hold renders as ITSELF, and every
  // assertion in the unit suite still passes. Four landed that way in one day.
  const leaked = body.match(/customers\.account\.units\.[A-Za-z.]+/g);
  if (leaked) {
    note("units", `RAW MESSAGE KEY ON SCREEN: ${JSON.stringify([...new Set(leaked)])}`);
  }

  console.log("step 6 · the two filters are OFFERED, and `Billed to` actually filters");
  // ⚠ **THE FIRST SPELLING OF THIS REPORTED `filter chips = []` OVER A PANEL
  // THAT IS ON THE SCREEN**, and a photograph is what settled it. `FilterBar`
  // renders ONE `<details>` panel with a `<legend>` per filter, not one chip
  // per filter — so a selector looking for `summary` per filter finds one
  // summary and no chips, truthfully, about the wrong thing. **A walkthrough
  // that cannot tell present from absent is worse than none, because it is
  // believed** (hard-won law 7's third habit).
  await page.locator("details summary", { hasText: /Filter/ }).first().click();
  await page.waitForTimeout(600);
  await page.screenshot({ path: `${OUT}/04-units-tab-filters-1440.png`, fullPage: true });
  const legends = await page.locator("details fieldset legend").allTextContents();
  note("units", `filters offered = ${JSON.stringify(legends.map((c) => c.trim()))}`);
  if (legends.length !== 2) {
    note("units", `DEFECT: ${legends.length} filter(s) offered, the tab declares TWO`);
  }

  console.log("step 7 · what a VACANT row actually prints, cell by cell");
  // The whole point of the tab, read off the rendered page rather than the
  // payload: a vacant unit must say who pays, and must never print `$0.00`.
  const vacantRow = page
    .locator("tbody tr")
    .filter({ has: page.locator('[data-billed-to="this-account"]') })
    .filter({ hasNot: page.locator('[data-occupant-state="common-area"]') })
    .first();
  if ((await vacantRow.count()) > 0) {
    const cells = await vacantRow.locator("td").allTextContents();
    note("units", `a vacant row reads ${JSON.stringify(cells.map((c) => c.trim()))}`);
    const text = cells.join(" ");
    if (/\$\s*0\.00/.test(text)) {
      note("units", "DEFECT: a vacant row prints $0.00 (DEF-138) — it was never measured");
    }
  } else {
    note("units", "no vacant row billed here to read — nothing to check");
  }

  console.log("step 8 · an ORDINARY account must NOT show the tab");
  await page.goto(`${WEB}/${TENANT}/accounts?f.kind=regular`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  const ordinaryDoor = await page.locator("tbody tr td a").first().getAttribute("href");
  if (ordinaryDoor) {
    await page.goto(`${WEB}${ordinaryDoor}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(2000);
    await page.screenshot({ path: `${OUT}/05-ordinary-account-1440.png`, fullPage: true });
    const ordinaryTabs = await page.locator('[role="tab"]').allTextContents();
    note("regular", `tab strip = ${JSON.stringify(ordinaryTabs)}`);
    if (ordinaryTabs.includes("Units")) {
      note("regular", "DEFECT: the Units tab is offered on an ORDINARY account");
    }
  } else {
    note("regular", "no ordinary account in this tenant to check against");
  }
} finally {
  console.log("\n══ findings ══");
  console.log(findings.join("\n"));
  console.log(`\nscreenshots in ${OUT}`);
  await browser.close();
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: `BR-CUS-1094` (PO 2026-09-23)
// generated: 2026-09-23 by lane MA-UNITS
// gates: this IS the gate that no other gate is — hard-won law 6. Its own
//        red proof is that it reported a DEAD DOOR when run against a build
//        whose `accountTabIds` did not carry `units`, and a `MISSING` on the
//        Billed to column when run with the column removed.
// exceptions: E4 it exits 0 with a named reason when the tenant holds no
//   master account: *nothing to look at* and *the screen is broken* are
//   different facts, and a walkthrough that conflates them gets believed
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
