// ── Trace ──────────────────────────────────────────────
// Story:   CR-142-BRC07 Phase 2 · `P2.24` — *"Drill down in place. A group row
//          expands to the next level WITHOUT LEAVING THE REPORT — Area opens
//          its routes, a route its premises. Collapse restores it."*
//          Outcome: *"Three levels open and close without a page load."*
// Rules:   CLAUDE.md hard-won law 6 (*"diff the running app — no gate looks at
//          rendered output"*) · law 2's mirror · B14 rule 44 (a staff screen is
//          built at 1440 and must work at 1280).
// ───────────────────────────────────────────────────────
//
// PHOTOGRAPH WHAT IS THERE. No CSS is injected, no element is hidden and no
// value is substituted. Where a state cannot be reached the script SAYS SO in
// 00-README.txt rather than skipping it silently — an absence with no reason
// beside it is indistinguishable from a pass (hard-won law 7's fifth shape).
//
//   node 10-scripts/rep_p2_24_shots.mjs
//
// Env: SMOKE_BASE (http://127.0.0.1:8090) · SMOKE_TENANT · SMOKE_EMAIL ·
//      SMOKE_PASSWORD · SHOT_OUT
//
// ⚠ **THE REQUEST COUNT IS PART OF THE PHOTOGRAPH.** *"No page load"* is the
// whole task, so this script counts every `/api/{tenant}/reports/…` request the
// browser makes and prints the count across an open and a close. A screenshot
// of an expanded tree proves the tree; only the counter proves it was free.

import { mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";

// No dependency of its own — it borrows `playwright-core` from the front end's
// install, exactly as `cr142_p2_22_shots.mjs` and `12-smoke-walkthrough.mjs` do.
const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:8090";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SHOT_OUT ?? "/tmp/p2-24-shots";
const EXE = process.env.PW_CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

const REPORT = process.env.REP_KEY ?? "trend_pack";
const GROUPING = process.env.REP_GROUPING ?? "year,accounting_period,service";

const notes = [];
function note(line) {
  console.log(line);
  notes.push(line);
}

async function shot(page, name, width) {
  await page.setViewportSize({ width, height: 1100 });
  await page.waitForTimeout(700);
  await page.screenshot({ path: `${OUT}/${name}-${width}.png`, fullPage: true });
  note(`  shot ${name}-${width}.png`);
}

/** Every disclosure on screen, in document order, with its state. */
async function disclosures(page) {
  return page.$$eval("[data-group-disclosure]", (nodes) =>
    nodes.map((n) => ({
      state: n.getAttribute("data-group-disclosure"),
      name: n.getAttribute("aria-label"),
    })),
  );
}

async function main() {
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ executablePath: EXE });
  const context = await browser.newContext();
  const page = await context.newPage();

  // ⚠ THE COUNTER. Only report READS count — the toolbar's lookups and the
  // catalogue are a different question and would mask the one being asked.
  let reportReads = 0;
  page.on("request", (req) => {
    if (/\/api\/[^/]+\/reports\/[^/?]+/.test(req.url())) reportReads += 1;
  });

  // ⚠ `/signin`, `#signin-email`, `#signin-password` — the ids the shipped
  // screen actually uses. `cr142_p2_22_shots.mjs` records the same three.
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForTimeout(2500);
  note(`signed in as ${EMAIL}; landed on ${page.url()}`);

  const url = `${BASE}/${TENANT}/reports/${REPORT}?group_by=${encodeURIComponent(GROUPING)}`;
  await page.goto(url, { waitUntil: "networkidle" });
  note(`opened ${url}`);

  const version = await page.locator("text=/v?2\\.\\d+\\.\\d+/").first().textContent().catch(() => null);
  note(`version on screen: ${version ?? "NOT FOUND — reported rather than assumed"}`);

  // ⚠ **WAIT FOR THE ROW BEFORE COUNTING IT.** The first run of this script
  // counted immediately after `networkidle` and got `0 body rows · 0
  // disclosures` over a screen that was drawing the group row correctly — a
  // zero that read exactly like *"the control is not wired"*. A count taken
  // before the paint is law 7's *looking at the wrong thing*, and it nearly
  // sent this lane back into working code.
  await page.waitForSelector("[data-group-disclosure]", { timeout: 15000 }).catch(() => null);
  let rows = await page.locator("table tbody tr").count();
  let open = await disclosures(page);
  note(`RESTING: ${rows} body rows · ${open.length} disclosures · states ${JSON.stringify(open.map((d) => d.state))}`);
  await shot(page, "01-closed", 1440);
  await shot(page, "01-closed", 1280);

  if (open.length === 0) {
    note("STOP — no disclosure on screen. Either the grouping was not served or the control is not wired. Nothing below can be photographed.");
  } else {
    const afterLoad = reportReads;

    await page.click('[data-group-disclosure="closed"]');
    await page.waitForTimeout(400);
    rows = await page.locator("table tbody tr").count();
    note(`LEVEL 1 OPEN: ${rows} body rows · report reads since load: ${reportReads - afterLoad}`);
    await shot(page, "02-level1-open", 1440);

    const stillClosed = await page.$('[data-group-disclosure="closed"]');
    if (stillClosed) {
      await stillClosed.click();
      await page.waitForTimeout(400);
      rows = await page.locator("table tbody tr").count();
      note(`LEVEL 2 OPEN: ${rows} body rows · report reads since load: ${reportReads - afterLoad}`);
      await shot(page, "03-level2-open", 1440);
      await shot(page, "03-level2-open", 1280);
    } else {
      note("NOTE: nothing further to open — this report groups one level deep. Reported, not skipped.");
    }

    await page.click('[data-group-disclosure="open"]');
    await page.waitForTimeout(400);
    rows = await page.locator("table tbody tr").count();
    open = await disclosures(page);
    note(`COLLAPSED AGAIN: ${rows} body rows · ${open.length} disclosures · report reads since load: ${reportReads - afterLoad}`);
    await shot(page, "04-collapsed-again", 1440);

    note(
      reportReads - afterLoad === 0
        ? "PASS · ZERO report reads across open, open and close — *no page load*, measured."
        : `FAIL · ${reportReads - afterLoad} report read(s) during open/close. This is a drill-THROUGH, not a drill-down.`,
    );
  }

  writeFileSync(`${OUT}/00-README.txt`, notes.join("\n") + "\n");
  await browser.close();
}

main().catch((err) => {
  console.error(err);
  writeFileSync(`${OUT}/00-README.txt`, notes.concat([`ERROR: ${err.message}`]).join("\n") + "\n");
  process.exit(1);
});
