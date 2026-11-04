/**
 * RENDERED-OUTPUT CHECK — CR-075 wave G task `G5` and wave H task `H5`.
 * Runbook 24 on `RBS-006` and the work list on `RBS-007`, in a real browser,
 * against `wireframes/RBS-006-R24.md` and `wireframes/RBS-007.1___RBS-007.2`.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: *"no gate looks at rendered output"*,
 * and nine defects were found by that and by nothing else. And the Product
 * Owner's own definition of done, 2026-09-06: *"ensure you do web walkthorugh
 * before you sign off the user story or build"*.
 *
 * ⚠ **THE STRONGEST ASSERTION IN THIS FILE IS THE ONE THAT CLICKS.** A grid
 * cell's `href` merely LOOKING right is what `DEF-RBS-4329` and `DEF-RBS-4354`
 * both cost: a tenant-relative route handed straight to `<Link to>` resolves
 * against the CURRENT route and produces `…/runs/<grid>/runbooks/test_bill/
 * runs/<cell>` — a perfectly good string that opens onto nothing. So this
 * check **presses a cell and reads the screen it lands on**, which is the only
 * thing that can tell the two apart.
 *
 * ⚠ **AND THE RUN IS EXECUTED, NOT INSERTED.** `rbs_g_seed_coverage.py` runs
 * runbooks 1 and 24 through `services.run_to_completion`, so every report is
 * composed by `report()` and frozen by `close_run`, and every work item is
 * written by `engine/work_items.py` at close. A fixture that TYPED a block list
 * or an item row would let this walkthrough pass over a broken engine —
 * `DEF-RBS-4291`'s shape exactly.
 *
 * ⚠ **STARTING A RUN FROM THE SCREEN IS NOT POSSIBLE YET AND IS SAID RATHER
 * THAN SUBSTITUTED.** `POST /runbooks/{key}/runs` is wave `L`; every runbooks
 * route that exists today is a `GET` except `PATCH /work-items/{id}`, which
 * this file DOES press. The click-to-start half is `L`'s walkthrough.
 *
 * ── HOW TO RUN IT ────────────────────────────────────────────────────────
 *   Use a database NOBODY ELSE is seeding.
 *
 *   createdb sbh_rbsgh -T sbh_rbsf
 *   DJANGO_SETTINGS_MODULE=config.settings.local DATABASE_URL=…/sbh_rbsgh \
 *     python3.12 06-backend/manage.py migrate
 *   DJANGO_SETTINGS_MODULE=config.settings.local DATABASE_URL=…/sbh_rbsgh \
 *     python3.12 10-scripts/render-checks/rbs_g_seed_coverage.py --tenant brazosbend
 *   … it prints SMOKE_RUN_GRID, SMOKE_RUN_CHECK and SMOKE_CELLS.
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local DATABASE_URL=…/sbh_rbsgh \
 *     python3.12 06-backend/manage.py runserver 127.0.0.1:8099 --noreload &
 *   (cd 07-frontend && ./node_modules/.bin/vite build && \
 *      PORT=4299 API_PROXY_TARGET=http://127.0.0.1:8099 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4299 SMOKE_RUN_GRID=… SMOKE_CELLS=3 \
 *   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/rbs-g-coverage-grid.mjs
 *
 * ── WHAT IT ASSERTS ──────────────────────────────────────────────────────
 *   THE GRID (`RBS-006-R24`)
 *   1  the report is the three blocks the sheet draws, in order.
 *   2  the KPI strip carries FOUR tiles and the three outcomes SUM to the
 *      fourth — the denominator that stops *3 clean* over an estate of 400
 *      reading as a perfect result (hard-won law 7).
 *   3  the grid drew one CELL per record, each coloured by its outcome, and
 *      the count on screen is the count in the frozen report.
 *   4  the sentence names what the pick LEFT OUT (`TC-RBS-005.5`).
 *   5  **a cell is CLICKED** and the screen it lands on is that account's own
 *      test bill — asserted by the ADDRESS and by what the page says.
 *   6  B14 rules 31 and 32 — no database id and no rule id anywhere a clerk
 *      can read.
 *   7  the page does not scroll sideways at 1440.
 *
 *   THE WORK LIST (`RBS-007`)
 *   8  the six columns the sheet draws, in that order.
 *   9  every row raised by a Check names the runbook that raised it and links
 *      to the run — and the AGE is the FIRST sighting.
 *  10  the chips carry the SERVER's counts, not the page's.
 *  11  **Resolve is PRESSED** and the row leaves the open list — the one
 *      write this module's screens can perform today.
 */
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  const roots = [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean);
  for (const root of roots) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of [
        "chrome-linux64/chrome",
        "chrome-linux/chrome",
        "chrome-linux/headless_shell",
      ]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  return undefined;
}

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4299";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const GRID = process.env.SMOKE_RUN_GRID ?? "";
const CELLS = Number(process.env.SMOKE_CELLS ?? "0");
const OUT = process.env.SMOKE_OUT ?? "/tmp/rbs-g-coverage-grid";
const VIEWPORT = { width: 1440, height: 1000 };

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

const SIDEWAYS =
  "Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)";

/** Anything a clerk must never be shown (B14 rules 31 and 32). */
const FORBIDDEN_IN_CLERK_COPY = [
  /\bBR-[A-Z]{3}-\d{3,5}\b/,
  /\b(?:OQ|DEF|TC|US|EP|GT|RB)-(?:[A-Z]{3}-)?\d{2,5}\b/,
  /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
];

if (GRID === "") {
  console.error(
    "⛔ SMOKE_RUN_GRID is not set. This check reads STORED runs — it cannot start one,\n" +
      "   because POST /runbooks/{key}/runs is wave L. Run rbs_g_seed_coverage.py first.",
  );
  process.exit(2);
}
if (CELLS < 2) {
  console.error(
    `⛔ SMOKE_CELLS is ${CELLS}. One cell reads '1 clean' and looks perfect; a walkthrough\n` +
      "   over one cell proves nothing (hard-won law 7). The seed refuses below two too.",
  );
  process.exit(2);
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });

  // The server's own answer, captured rather than inferred. *Did the screen
  // draw it* and *did the server send it* are two different questions, and
  // `DEF-RBS-4284` is what happens when only one of them is asked.
  const wire = [];
  page.on("response", async (response) => {
    if (!/\/(runbooks|work-items)\b/.test(response.url())) return;
    try {
      wire.push({ url: response.url(), body: await response.text() });
    } catch {
      /* a redirect or a bodyless response has nothing to read */
    }
  });

  console.log("── sign in ───────────────────────────────────────────────");
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/dashboard(\?|$)/, { timeout: 30000 });

  // ══════════════════════════════════════════════════════════════════════
  // THE GRID — `RBS-006-R24`
  // ══════════════════════════════════════════════════════════════════════
  console.log("── RBS-006-R24 · the coverage grid ───────────────────────");
  wire.length = 0;
  await page.goto(`${BASE}/${TENANT}/runbooks/coverage_grid/runs/${GRID}`, {
    waitUntil: "networkidle",
  });
  await page.screenshot({ path: join(OUT, "rbs-006-r24-grid.png"), fullPage: true });

  const body = (await page.textContent("body")) ?? "";
  const reportBody = wire.find((w) => /\/report\b/.test(w.url))?.body ?? "";
  const blocks = reportBody === "" ? [] : (JSON.parse(reportBody).blocks ?? []);
  check(
    JSON.stringify(blocks.map((b) => b.block)) === JSON.stringify(["kpis", "records", "sentence"]),
    `1 · the report is the three blocks the sheet draws (saw ${blocks.map((b) => b.block).join(", ")})`,
  );

  // 2 · the KPI strip, and the denominator that makes the other three mean
  //     something.
  // ⚠ **THE TILE NODES, AND THE SELECTOR IS ASSERTED TO MATCH SOMETHING.** A
  // `$$eval` over a selector that matches nothing returns `[]` and every
  // `find` over it is `undefined` — a check that cannot fail (law 7). The
  // count is asserted against the payload's below.
  // ⚠ **`.kpi` IS `KPIStrip`'s OWN CLASS AND THE SELECTOR IS ASSERTED TO MATCH
  // SOMETHING.** A `$$eval` over a selector that matches nothing returns `[]`,
  // every `find` over it is `undefined`, and the checks below then pass or fail
  // for a reason that has nothing to do with the screen — a check that cannot
  // fail, or one that cannot pass. The first draft of this block guessed
  // `[data-block='kpis']`, which `KpisBlock` does not emit, and reported
  // *0 node(s)* rather than pretending.
  const tiles = await page.$$eval(".kpi-grid .kpi", (nodes) =>
    nodes.map((n) => (n.textContent ?? "").replace(/\s+/g, " ").trim()),
  );
  check(tiles.length > 0, `2 · the KPI strip drew something at all (${tiles.length} node(s))`);
  const strip = blocks.find((b) => b.block === "kpis")?.payload?.tiles ?? [];
  // `KpisPayload.tiles[].value` is a `ReportValue` — `{kind: "text", text}` —
  // and not a bare string. Reading `t.value` here gave `NaN` for every tile and
  // the sum check then compared NaN with NaN, which is false, which LOOKED like
  // a failing assertion about the product (`DEF-RBS-4375`'s own shape one more
  // time, in the check written for it).
  const numbers = strip.map((t) => Number(t.value?.text ?? t.value));
  check(
    strip.length === 4 && numbers[0] + numbers[1] + numbers[2] === numbers[3],
    `2 · four tiles and the three outcomes sum to the fourth (${numbers.join(" + ")} over ${numbers[3]})`,
  );
  for (const tile of strip) {
    // ⚠ **THE VALUE, NOT ONLY THE LABEL — `DEF-RBS-4375`.** This asserted the
    // LABEL alone and passed over a strip of FOUR EMPTY BOXES: `CLEAN`,
    // `ESTIMATED`, `REFUSED` and `CELLS` drawn with no numbers under them,
    // because the tiles carried `value` as a bare string where `KpisPayload`
    // declares a `ReportValue`. The screenshot said so after this check had
    // already reported a pass — a check whose output cannot distinguish pass
    // from fail is worse than no check, because it is trusted.
    const drawn = tiles.find((text) => text.includes(tile.label));
    check(
      drawn !== undefined && drawn.includes(String(tile.value.text ?? tile.value)),
      `2 · the strip drew "${tile.label}" WITH its number (${String(tile.value.text ?? tile.value)}) — saw ${JSON.stringify(drawn ?? null)}`,
    );
  }
  console.log(`   (tiles as drawn: ${tiles.slice(0, 8).join(" | ")})`);

  // 3 · one CELL per record, coloured by outcome.
  const cells = await page.$$("[data-record-cell]");
  const states = await page.$$eval("[data-record-cell]", (nodes) =>
    nodes.map((n) => n.getAttribute("data-record-state")),
  );
  const records = blocks.find((b) => b.block === "records")?.payload ?? {};
  check(
    cells.length === (records.rows ?? []).length && cells.length === CELLS,
    `3 · the grid drew ${cells.length} cell(s); the frozen report holds ${(records.rows ?? []).length} and the seed said ${CELLS}`,
  );
  check(
    states.every((s) => ["clean", "estimated", "refused"].includes(s ?? "")),
    `3 · every cell carries one of the three outcomes (${states.join(", ")})`,
  );
  check(
    records.display === "grid",
    "3 · it is the `records` block in GRID mode and not a thirteenth block (BR-RBS-021)",
  );

  // 4 · the sentence names what the pick LEFT OUT — `TC-RBS-005.5`.
  const sentence = blocks.find((b) => b.block === "sentence")?.payload?.text ?? "";
  check(
    sentence !== "" && body.includes(sentence),
    `4 · the sentence is on the page: "${sentence}"`,
  );
  check(
    /combinations were priced/.test(sentence),
    "4 · it says how many combinations were priced rather than truncating in silence",
  );

  // 6 · B14 rules 31 and 32, over everything a reader can see.
  for (const pattern of FORBIDDEN_IN_CLERK_COPY) {
    check(!pattern.test(body), `6 · nothing matching ${pattern} reaches a clerk`);
  }

  // 7 · the page does not scroll sideways.
  check((await page.evaluate(SIDEWAYS)) === 0, "7 · no horizontal scroll at 1440");

  // ══════════════════════════════════════════════════════════════════════
  // 5 · THE CLICK — a cell opens THAT ACCOUNT'S test bill
  // ══════════════════════════════════════════════════════════════════════
  console.log("── the click ─────────────────────────────────────────────");
  const firstLabel = (await cells[0].textContent())?.trim() ?? "";
  await cells[0].click();
  // ⚠ **WAIT FOR THE BLOCK, NOT FOR THE NETWORK.** This is a CLIENT-SIDE
  // navigation, so `networkidle` returns while the new screen is still a
  // loading skeleton — and a body read at that moment holds none of the
  // destination's words. The first run of this check failed here for exactly
  // that reason and the screen was fine.
  await page.waitForSelector("[data-block]", { timeout: 20000 });
  await page.waitForLoadState("networkidle");
  const landed = page.url();
  check(
    /\/runbooks\/test_bill\/runs\/[0-9a-f-]{36}$/.test(landed.replace(BASE, "")),
    `5 · the cell landed on the test bill's own run — ${landed.replace(BASE, "")}`,
  );
  const cellBody = (await page.textContent("body")) ?? "";
  check(
    /Test bill/i.test(cellBody),
    "5 · and the screen it opened says so — not `This screen is not built yet.`",
  );
  check(
    !/not built yet/i.test(cellBody),
    "5 · the destination is a live screen (DEF-CWP-3925's mirror)",
  );
  console.log(`   (the cell read "${firstLabel.split("\n")[0]}")`);
  await page.screenshot({ path: join(OUT, "rbs-006-r23-from-a-cell.png"), fullPage: true });

  // ══════════════════════════════════════════════════════════════════════
  // THE WORK LIST — `RBS-007`
  // ══════════════════════════════════════════════════════════════════════
  console.log("── RBS-007 · the work list ───────────────────────────────");
  wire.length = 0;
  await page.goto(`${BASE}/${TENANT}/runbooks/work`, { waitUntil: "networkidle" });
  await page.screenshot({ path: join(OUT, "rbs-007-work-list.png"), fullPage: true });

  const listBody = (await page.textContent("body")) ?? "";
  const served = wire.find((w) => /\/work-items\?/.test(w.url) || /\/work-items$/.test(w.url));
  const payload = served === undefined ? null : JSON.parse(served.body);
  check(payload !== null, "8 · the server served the work list");

  const headers = await page.$$eval("th", (nodes) =>
    nodes.map((n) => (n.textContent ?? "").replace(/[⇅↑↓]/g, "").trim()).filter(Boolean),
  );
  check(
    JSON.stringify(headers.slice(0, 6)) ===
      JSON.stringify(["What needs doing", "From", "Weight", "Owner", "Age", "Actions"]),
    `8 · the six columns the sheet draws, in that order (saw ${headers.slice(0, 6).join(" | ")})`,
  );

  // 9 · a Check's row names the runbook and links to the run.
  const runLinks = await page.$$eval("[data-work-run]", (nodes) =>
    nodes.map((n) => ({ text: (n.textContent ?? "").trim(), href: n.getAttribute("href") })),
  );
  check(runLinks.length > 0, `9 · ${runLinks.length} row(s) name the run that raised them`);
  check(
    runLinks.every((l) => (l.href ?? "").startsWith(`/${TENANT}/runbooks/`)),
    "9 · and each link is the TENANT's address, not a relative one (DEF-RBS-4329)",
  );
  const ages = await page.$$eval("[data-work-age]", (nodes) =>
    nodes.map((n) => (n.textContent ?? "").trim()),
  );
  check(
    ages.length > 0 && ages.every((a) => /^(Today|\d+ days?)$/.test(a)),
    `9 · the age reads as days from the FIRST sighting (${ages.slice(0, 4).join(", ")})`,
  );

  // 10 · the chips carry the SERVER's counts.
  const chipText = await page.$$eval("[data-chips='work'] button", (nodes) =>
    nodes.map((n) => (n.textContent ?? "").trim()),
  );
  const chips = payload?.chips ?? {};
  check(
    chipText[0] === `All ${chips.all}`,
    `10 · the All chip is the server's total (${chipText[0]} against ${chips.all})`,
  );
  check(
    chipText[1] === `Blocks billing ${chips.blocks_billing}`,
    `10 · Blocks billing is the server's count (${chipText[1]})`,
  );

  // 11 · PRESS Resolve. The one write these screens can perform today.
  const before = (await page.$$("tbody tr")).length;
  const resolve = await page.$('button[aria-label="Resolve"]');
  check(resolve !== null, "11 · a Resolve control is on the row");
  if (resolve !== null) {
    await resolve.click();
    await page.waitForTimeout(1500);
    const after = (await page.$$("tbody tr")).length;
    check(
      after === before - 1,
      `11 · the resolved row left the open list (${before} → ${after})`,
    );
  }

  for (const pattern of FORBIDDEN_IN_CLERK_COPY) {
    check(!pattern.test(listBody), `11 · nothing matching ${pattern} reaches a clerk here either`);
  }
  check((await page.evaluate(SIDEWAYS)) === 0, "11 · no horizontal scroll at 1440");

  await browser.close();

  console.log("\n──────────────────────────────────────────────────────────");
  if (failures.length > 0) {
    console.error(`⛔ ${failures.length} check(s) failed:`);
    for (const one of failures) console.error(`   · ${one}`);
    process.exit(1);
  }
  console.log(`✓ every check passed. Screenshots in ${OUT}`);
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
