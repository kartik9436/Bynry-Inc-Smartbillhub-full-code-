// ── Trace ──────────────────────────────────────────────
// Journey:  08-qa/01-e2e/journeys/JPAYLOCKBOX-a-store-file-on-a-monday-morning.md
// Change:   `CR-135-BRC07` `P1.14` — the walk that journey was written for and
//           had never been run. Checks **M** (Source on the screen) and **N**
//           (the run's number on the screen) are read off the rendered page.
// Rules:    CLAUDE.md hard-won law 6 (no gate in this repo reads rendered
//           output) · law 2 (built is not wired, and its mirror: a live screen
//           behind a dead control) · law 7 (a check that cannot tell present
//           from absent is worse than none) · B14 rule 31 (no database id is
//           the visible value of a field, and an ADDRESS BAR is a visible
//           field)
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT THIS ASKS THAT NO SUITE CAN
// ══════════════════════════════════════════════════════════════════════════
// The journey's own sentence: *"a walk that ends at the receipt passes over
// the two checks that matter — the receipt is written by the same code that
// did the load, so it will agree with itself whatever happened."* So this
// script never reads a count off the receipt and calls it proved; it presses
// the buttons and then `jpaylockbox_readback.py` asks the DATABASE.
//
// ⚠ **IT BOOTS NOTHING, ON PURPOSE** — `11-smoke-stack.sh` tears its stack
// down on exit, which is right for a smoke run and wrong for a nine-step walk
// you want to photograph. Point it at an already-running SPA join:
//
//     10-scripts/proof-db.sh clone lockbox            # a REAL PostgreSQL 16
//     cd 06-backend && DATABASE_URL=… python3 manage.py runserver 127.0.0.1:8311 --noreload &
//     cd 07-frontend && ./node_modules/.bin/vite build
//     PORT=8312 API_PROXY_TARGET=http://127.0.0.1:8311 node server.mjs &
//     DATABASE_URL=… python3 10-scripts/jpaylockbox_seed_store_file.py --out /tmp/lockbox
//     PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers WEB=http://127.0.0.1:8312 \
//       FIXTURE=/tmp/lockbox node 10-scripts/jpaylockbox_walkthrough.mjs
//
// ⚠ **A WALKTHROUGH THAT CANNOT TELL PRESENT FROM ABSENT IS WORSE THAN NONE.**
// Every selector below is the one the component actually renders, read from
// its source, and the two that were wrong on the first run are named where
// they are used:
//   · `button:has-text("Transform")` matches the disabled STAGE-BAR button
//     before it matches the footer's `Transform →`. The arrow is load-bearing.
//   · the mapping `<select>`s are scoped `[data-workflow="mapping"] select`;
//     page-wide, the Extract stage's own pickers are counted as mapping rows.
import { mkdirSync, existsSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome", "chrome-linux/headless_shell"]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  throw new Error("no chromium found — and `playwright install` is forbidden here");
}

const WEB = process.env.WEB || "http://127.0.0.1:8312";
const TENANT = process.env.SMOKE_TENANT || "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const FIXTURE = process.env.FIXTURE || "/tmp/claude-0/lane-p01/fixture";
const OUT = process.env.OUT || "/tmp/claude-0/lane-p01/shots";
mkdirSync(OUT, { recursive: true });

const manifest = JSON.parse(readFileSync(join(FIXTURE, "manifest.json"), "utf8"));
const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;

const findings = [];
function note(step, what) {
  findings.push(`[${step}] ${what}`);
  console.log(`  · ${step}: ${what}`);
}
const squash = (s) => (s || "").replace(/\s+/g, " ").trim();

/** Every stage's own counters, read off the page rather than off the API. */
async function stageCounts(page) {
  const cells = await page.locator("[data-workflow='counts'] dd, .wf-count, dl dd").allTextContents();
  const labels = await page.locator("[data-workflow='counts'] dt, dl dt").allTextContents();
  return labels.map((l, i) => `${squash(l)}=${squash(cells[i] ?? "")}`);
}

async function signIn(page) {
  await page.goto(`${WEB}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(`**/${TENANT}/dashboard`, { timeout: 30000 });
}

/** Stage 1 → stage 3, with one file. Returns what stage 3 said about it. */
async function runToValidate(page, file, label) {
  await page.goto(`${WEB}/${TENANT}/payments/imports/new`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  await page.setInputFiles('input[type="file"]', file);
  await page.waitForTimeout(3500);

  // ── step 4 of the journey, drawn on stage ONE rather than after mapping.
  const insert = page.locator('input[type="radio"][value="insert"]');
  const upsert = page.locator('input[type="radio"][value="upsert"]');
  note(
    `${label}·write-mode`,
    `Insert checked=${await insert.isChecked()} · Insert & update disabled=${await upsert.isDisabled()}`,
  );

  // ⚠ THE ARROW IS LOAD-BEARING — see the header.
  await page.click('button:not([data-workflow-stage]):has-text("Transform →")');
  await page.waitForTimeout(3000);
  await page.screenshot({ path: `${OUT}/${label}-02-transform.png`, fullPage: true });

  // ── step 3 · map the six columns by hand.
  const selects = page.locator('[data-workflow="mapping"] select');
  const count = await selects.count();
  const sources = await page.locator('[data-workflow="mapping"] tbody tr td:first-child').allTextContents();
  note(`${label}·map`, `${count} source column(s): ${JSON.stringify(sources.map(squash))}`);
  const auto = [];
  for (let i = 0; i < count; i += 1) auto.push(await selects.nth(i).inputValue());
  note(`${label}·map`, `auto-mapped as ${JSON.stringify(auto)} — anything __ignore__ is mapped BY HAND below`);

  // The store's names → ours. `STORE` is left unmapped DELIBERATELY: journey
  // step 3 asks that an unmapped column be SHOWN and NAMED, not that it be
  // forced somewhere.
  const byHand = {
    "CUST REF": "account_ref",
    PAID: "amount",
    WHEN: "paid_on",
    "TILL SLIP": "reference",
    "NAME ON STUB": "payer_name",
  };
  for (const [source, target] of Object.entries(byHand)) {
    const select = page.locator(`[data-workflow="mapping"] select[aria-label="Maps ${source} to"]`);
    if ((await select.count()) === 0) {
      note(`${label}·map`, `NO PICKER for ${source} — the column is not on the mapping table`);
      continue;
    }
    await select.selectOption(target);
    await page.waitForTimeout(250);
  }
  await page.waitForTimeout(1500);
  const statuses = await page.locator("[data-workflow-map-status]").evaluateAll((rows) =>
    rows.map((r) => `${r.querySelector("td")?.textContent?.trim()}=${r.getAttribute("data-workflow-map-status")}`),
  );
  note(`${label}·map`, `row statuses after mapping: ${JSON.stringify(statuses)}`);
  const storeRow = statuses.find((s) => s.startsWith("STORE"));
  note(
    `${label}·map`,
    storeRow
      ? `STORE is shown on the mapping table as ${storeRow} — journey step 3's "named, never silently dropped"`
      : "STORE IS NOT ON THE MAPPING TABLE — a column silently dropped",
  );
  await page.screenshot({ path: `${OUT}/${label}-03-mapped.png`, fullPage: true });

  await page.click('button:not([data-workflow-stage]):has-text("Validate →")');
  await page.waitForTimeout(6000);
  await page.screenshot({ path: `${OUT}/${label}-04-validate.png`, fullPage: true });
  const body = squash(await page.textContent("body"));
  return body;
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
page.on("pageerror", (e) => note("console", `PAGE ERROR: ${e.message}`));
const result = { runNumber: null, findings };

try {
  console.log("── sign in");
  await signIn(page);

  // ══ STEP 1 · Payments → Imports ═════════════════════════════════════════
  console.log("step 1 · Payments → Imports");
  await page.goto(`${WEB}/${TENANT}/payments/imports`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `${OUT}/01-imports-tab.png`, fullPage: true });
  const h1 = squash(await page.textContent("h1"));
  note("step 1", `page head reads ${JSON.stringify(h1)}`);
  const importDoors = await page.locator('button:has-text("Import"), a:has-text("Import")').count();
  note("step 1", `${importDoors} control(s) whose word is Import — 4·1 draws ONE door`);
  const rollbackControls = await page.locator('button:has-text("Roll back"), button:has-text("Rollback"), a:has-text("Roll back")').count();
  note(
    "check L",
    `${rollbackControls} rollback control(s) on the run list — the journey requires ZERO (a posted payment cannot be unwritten)`,
  );

  // ══ STEP 2a · THE FILE AS THE STORE SENDS IT ════════════════════════════
  console.log("step 2a · the file as the store sends it — $ and a two-digit year");
  const asSent = await runToValidate(page, manifest.file_as_sent, "as-sent");
  for (const phrase of ["is not a number", "not a date", "does not match", "Rows checked", "rejected"]) {
    if (asSent.includes(phrase)) note("step 2a", `stage 3 says ${JSON.stringify(phrase)}`);
  }
  const asSentPanel = squash(
    (await page.locator("main").textContent().catch(() => "")) || asSent,
  ).slice(0, 1800);
  note("step 2a", `stage 3 on the store's own file: ${asSentPanel}`);

  // ══ STEP 2b · THE SAME FILE AFTER THE HAND EDITS ════════════════════════
  console.log("step 2b · the same file after the two hand edits a clerk must make");
  await page.goto(`${WEB}/${TENANT}/payments/imports/new`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  const cards = await page.locator("main").textContent();
  note(
    "step 2",
    squash(cards).includes("Scan paper")
      ? "Scan paper is drawn as the fifth source card"
      : "Scan paper is NOT drawn",
  );
  const scanRadio = page.locator('input[type="radio"][value="scan"]');
  note(
    "step 2",
    `Scan paper refused=${await scanRadio.isDisabled()} — with its reason on the card (P1.19)`,
  );

  const repaired = await runToValidate(page, manifest.file_repaired, "repaired");
  note("step 5", `stage 3 on the repaired file: ${repaired.slice(repaired.indexOf("Stage 3"), repaired.indexOf("Stage 3") + 2200)}`);

  // ══ STEP 6 · what the screen offers for the eleven name-only rows ═══════
  const rejectRows = await page.locator("table tbody tr").count();
  note("step 6", `${rejectRows} row(s) in the stage-3 tables`);
  const fixControls = await page.locator('button:has-text("Fix"), button:has-text("Edit"), button:has-text("Choose")').count();
  note("step 6", `${fixControls} per-row control(s) offering to place a stuck row from this screen`);
  const failuresLink = await page.locator('a:has-text("Download"), button:has-text("Download")').allTextContents();
  note("step 6 / check J", `download controls: ${JSON.stringify(failuresLink.map(squash))}`);

  // ══ STEP 7 · commit ═════════════════════════════════════════════════════
  console.log("step 7 · commit — stage 4 is the only stage that writes");
  const loadButton = page.locator('button:not([data-workflow-stage]):has-text("Load →")').first();
  const loadText = await loadButton.textContent().catch(() => null);
  note("step 7", `the commit control reads ${JSON.stringify(squash(loadText))}`);
  await loadButton.click();
  await page.waitForTimeout(3000);
  await page.screenshot({ path: `${OUT}/05-load-stage.png`, fullPage: true });
  const stageFour = (await page.locator("button:not([data-workflow-stage])").allTextContents()).map(squash);
  note("step 7", `stage 4 offers: ${JSON.stringify(stageFour)}`);
  const dryRun = squash(await page.textContent("main"));
  note("step 7 / dry run", dryRun.slice(dryRun.indexOf("Dry run"), dryRun.indexOf("Dry run") + 900));
  // ⚠ **CHECK J LIVES HERE AND NOT ON STAGE 3**, which is why the first run
  // reported no download control: the failures download is drawn on the DRY
  // RUN, beside the rejected count it belongs to.
  const failures = (await page.locator('button:has-text("Download"), a:has-text("Download")').allTextContents()).map(squash);
  note("check J", `failures download on stage 4: ${JSON.stringify(failures)}`);
  // The approval bar — an import past 5% rejected needs an Owner or an Admin.
  const boxes = await page.locator('label:has(input[type="checkbox"])').allTextContents();
  note("step 7", `tick boxes on stage 4: ${JSON.stringify(boxes.map(squash))}`);
  // ⚠ **`{ force: true }` IS NOT A SHORTCUT, IT IS THE ONLY WAY TO TICK THIS
  // BOX.** The kit's checkbox is `class="peer sr-only"` with a styled `<span
  // data-checkbox-mark>` drawn over it, so an ordinary `.check()` reports
  // *"the span intercepts pointer events"* and times out — which reads exactly
  // like an approval control that does not work.
  const approval = page.locator("#import-load-approved");
  if ((await approval.count()) > 0) {
    note("step 7", "this run is past the approval bar and an Owner or Admin has to tick a box before the commit is live");
    await approval.first().check({ force: true });
    await page.waitForTimeout(1000);
    note("step 7", `approval ticked = ${await approval.first().isChecked()}`);
  }
  const commit = page.locator('button:not([data-workflow-stage]):has-text("Commit load")').first();
  note("step 7", `commit control reads ${JSON.stringify(squash(await commit.textContent()))} · disabled=${await commit.isDisabled()}`);
  await commit.click();
  await page.waitForTimeout(20000);
  await page.screenshot({ path: `${OUT}/06-receipt.png`, fullPage: true });

  // ══ STEP 8 · the receipt ════════════════════════════════════════════════
  const receipt = squash(await page.textContent("main"));
  result.receipt = receipt;
  note("step 8", `receipt: ${receipt.slice(0, 2400)}`);
  // ⚠ **THE WHOLE RECEIPT IS SEARCHED, NOT A SLICE.** The first run read a
  // 1,800-character slice and reported `null`, which reads exactly like a
  // receipt that carries no number — so the slice was doing the check's job.
  const runNo = receipt.match(/IMP-\d{6}-\d+/);
  result.receiptRunNumber = runNo ? runNo[0] : null;
  note(
    "step 8 / check N",
    runNo
      ? `the receipt prints the run number ${runNo[0]}`
      : "THE RECEIPT PRINTS NO RUN NUMBER — check N asks for *the number step 8's receipt printed*, and there is none to assert",
  );
  const arithmetic = receipt.match(/Loaded(\d+)Rejected(\d+)Flagged for review(\d+)/);
  if (arithmetic) {
    const [, loaded, rejected, flagged] = arithmetic.map(Number);
    note(
      "step 8",
      `receipt arithmetic: loaded=${loaded} rejected=${rejected} flagged=${flagged} · the file held ${manifest.rows_total} rows · loaded+rejected=${loaded + rejected}`,
    );
    if (loaded + rejected !== manifest.rows_total) {
      note(
        "step 8",
        `⚠ ${manifest.rows_total - (loaded + rejected)} ROW(S) ARE ON NEITHER SIDE OF THE RECEIPT — money in the file that the receipt does not account for`,
      );
    }
  }
  if (UUID.test(receipt)) note("step 8", "B14 RULE 31 BREACH: something uuid-shaped is on the receipt");

  // ══ STEP 9 · back on the Imports list ═══════════════════════════════════
  console.log("step 9 · back on Payments → Imports");
  await page.goto(`${WEB}/${TENANT}/payments/imports`, { waitUntil: "networkidle" });
  await page.waitForTimeout(3000);
  await page.screenshot({ path: `${OUT}/07-imports-list-after.png`, fullPage: true });
  const listRows = await page.locator("tbody tr").count();
  note("step 9", `${listRows} run(s) on the list`);
  const firstRow = squash(await page.locator("tbody tr").first().textContent().catch(() => ""));
  note("step 9", `newest row reads ${JSON.stringify(firstRow)}`);
  // The number the LIST carries, kept apart from the one the receipt carries,
  // because whether they are the same thing is what check N is asking.
  const listed = firstRow.match(/IMP-\d{6}-\d+/);
  result.runNumber = listed ? listed[0] : result.receiptRunNumber;
  note("step 9", `the run's number on the list = ${JSON.stringify(result.runNumber)}`);
  const rollbackAfter = await page.locator('button:has-text("Roll back"), button:has-text("Rollback")').count();
  note("check L", `${rollbackAfter} rollback control(s) over a LOADED payments run — the journey requires ZERO`);

  // ══ CHECK M · Source on the screen ══════════════════════════════════════
  console.log("check M · Source · Post on the payments list");
  // ⚠ **S33 IS `/payments/record`, NOT `/payments`.** The bare address is the
  // SUMMARY tab, which carries no table at all — the first run reported both
  // columns absent from it, which reads exactly like a column that was never
  // built. `paymentsShared.PAYMENTS_TABS` is where the seven addresses are.
  await page.goto(`${WEB}/${TENANT}/payments/record`, { waitUntil: "networkidle" });
  await page.waitForTimeout(3500);
  await page.screenshot({ path: `${OUT}/08-payments-list.png`, fullPage: true });
  const headers = (await page.locator("thead th").allTextContents()).map(squash);
  note("check M", `columns on S33: ${JSON.stringify(headers)}`);
  note(
    "check M",
    headers.includes("Source") ? "the Source column IS drawn" : "THE SOURCE COLUMN IS ABSENT",
  );
  const sourceIndex = headers.indexOf("Source");
  if (sourceIndex >= 0) {
    const cells = (await page.locator(`tbody tr td:nth-child(${sourceIndex + 1})`).allTextContents()).map(squash);
    const tally = cells.reduce((acc, c) => ({ ...acc, [c]: (acc[c] ?? 0) + 1 }), {});
    note("check M", `Source cells on page 1: ${JSON.stringify(tally)}`);
  }
  const batchIndex = headers.indexOf("Batch");
  if (batchIndex >= 0) {
    const cells = (await page.locator(`tbody tr td:nth-child(${batchIndex + 1})`).allTextContents()).map(squash);
    const tally = cells.reduce((acc, c) => ({ ...acc, [c]: (acc[c] ?? 0) + 1 }), {});
    note("check N", `Batch cells on page 1: ${JSON.stringify(tally)}`);
    note(
      "check N",
      result.runNumber && cells.includes(result.runNumber)
        ? `the receipt's own number ${result.runNumber} is in the Batch column`
        : `THE RECEIPT'S NUMBER ${JSON.stringify(result.runNumber)} IS NOT IN THE BATCH COLUMN on page 1`,
    );
  } else {
    note("check N", "THE BATCH COLUMN IS ABSENT");
  }

  // ── the Source filter, DRIVEN THROUGH THE SCREEN ────────────────────────
  // ⚠ **A TYPED `?f.origin=import` DOES NOT FILTER THIS LIST**, and the first
  // run proved it: the pager still read *1–50 of 146*, which is every payment
  // the tenant has. `tableTypes.parseTableParams` reads `<prefix>f.<name>`,
  // so the bare spelling is ignored under BR-SHL-011's *only DECLARED filters
  // restore*. The journey says *filtering the list by Source → Post*, which is
  // a thing a clerk does with the control — so that is what this does, and the
  // address is READ BACK afterwards rather than typed in.
  const filterSummary = page.locator('details summary:has-text("Filter")').first();
  note("check M", `${await filterSummary.count()} filter control(s) on S33`);
  await filterSummary.click();
  await page.waitForTimeout(800);
  const sourceBox = page
    .locator('details fieldset:has(legend:has-text("Source")) label:has-text("Post") input[type="checkbox"]')
    .first();
  if ((await sourceBox.count()) === 0) {
    note("check M", "NO Source fieldset in the filter panel — the filter is not drawn");
  } else {
    await sourceBox.check({ force: true });
    await page.waitForTimeout(3500);
    await page.screenshot({ path: `${OUT}/09-payments-filtered-post.png`, fullPage: true });
    const pager = squash(
      await page.locator(".data-table-footer, [class*='pager'], .table-pager").first().textContent().catch(() => ""),
    );
    note("check M", `filtered to Source → Post · pager reads ${JSON.stringify(pager)}`);
    note("check M", `the address the filter produced = ${JSON.stringify(page.url().replace(WEB, ""))}`);
    // ⚠ **CELLS, NEVER THE BODY.** The first spelling searched the whole page
    // for the words Counter and Digital and reported a non-Post row visible —
    // it was reading the filter panel's own option labels. A check that
    // cannot tell a row from a control is worse than no check.
    const headersNow = (await page.locator("thead th").allTextContents()).map(squash);
    const sourceCol = headersNow.indexOf("Source");
    const cells = (await page.locator(`tbody tr td:nth-child(${sourceCol + 1})`).allTextContents()).map(squash);
    const tally = cells.reduce((acc, c) => ({ ...acc, [c]: (acc[c] ?? 0) + 1 }), {});
    note("check M", `Source cells while filtered: ${JSON.stringify(tally)}`);
    note(
      "check M",
      Object.keys(tally).every((k) => k === "Post")
        ? "every Source cell on the filtered page reads Post"
        : "⚠ A NON-POST ROW SURVIVED THE POST FILTER",
    );
  }
} catch (error) {
  note("ABORTED", `${error.message}`);
  await page.screenshot({ path: `${OUT}/99-aborted.png`, fullPage: true }).catch(() => {});
} finally {
  writeFileSync(join(OUT, "walk.json"), JSON.stringify(result, null, 2));
  console.log("\n══ EVERY FINDING, IN ORDER ══");
  for (const line of findings) console.log(line);
  console.log(`\nscreenshots + walk.json in ${OUT}`);
  await browser.close();
}
