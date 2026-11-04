// ── Trace ──────────────────────────────────────────────
// Defects: DEF-REP-7072 (opening the editor cut the statement from SEVEN
//          columns to ONE) · DEF-REP-7053 (the export worked and nothing drew
//          a Download button) · DEF-REP-7052 (no statement named what it is
//          about).
// Rules:   CLAUDE.md hard-won law 6 (*diff the running app — no gate looks at
//          rendered output*) · law 2 and its MIRROR · law 7 clause 3 (a
//          check's OUTPUT must distinguish pass from fail TO A READER) ·
//          B14 rule 31 · rule 44 (a staff screen is built at 1440 and works at
//          1280).
// ───────────────────────────────────────────────────────
//
//   node 10-scripts/rep_stmt_screen_walkthrough.mjs
//
// Env: SMOKE_BASE · SMOKE_TENANT · SMOKE_EMAIL · SMOKE_PASSWORD · SHOT_OUT ·
//      REP_ACCOUNT (the account uuid the statement opens on) · REP_UNIT (a unit
//      uuid carrying ledger lines — the nine-column subject and its two-part head)
//
// ⚠ **THE COLUMN COUNT IS TAKEN TWICE, THROUGH THE URL, WITH A CLICK BETWEEN
// THEM.** That is the whole point: the defect lives where the editor's
// vocabulary meets the runner's, and a fixture that mounts either half alone
// passes on it. So this opens the real address, counts the headers, presses
// **Edit**, waits for the panel to actually be there, and counts again.
//
// ⚠ **THE DOWNLOAD IS PROVED AGAINST A REAL FILE OVER HTTP, NOT AGAINST A
// RENDERED BUTTON.** A drawn control over a 404 is the defect one door along
// (`DEF-REP-6899`, measured on this very screen last week). So the script
// presses it, polls the job, fetches the artifact, and prints the STATUS, the
// HEADERS and the first bytes. A button that renders and answers 404 fails
// here loudly.
//
// ⚠ **EVERY NUMBER IS PRINTED BESIDE ITS NAME AND NOTHING IS SKIPPED
// SILENTLY.** Where a state cannot be reached the script SAYS SO in
// `00-README.txt`; an absence with no reason beside it is indistinguishable
// from a pass (law 7's fifth shape).
import { mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:8492";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SHOT_OUT ?? "/tmp/rep-stmt-shots";
const EXE = process.env.PW_CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const ACCOUNT = process.env.REP_ACCOUNT ?? "";

const notes = [];
let failures = 0;
function note(line) {
  console.log(line);
  notes.push(line);
}
function verdict(ok, line) {
  if (!ok) failures += 1;
  note(`${ok ? "PASS" : "FAIL"} · ${line}`);
}

async function shot(page, name, width) {
  await page.setViewportSize({ width, height: 1200 });
  await page.waitForTimeout(700);
  await page.screenshot({ path: `${OUT}/${name}-${width}.png`, fullPage: true });
  note(`  shot ${name}-${width}.png`);
}

const headers = (page) =>
  page.$$eval("table thead th", (cells) => cells.map((c) => c.textContent.trim()));

async function main() {
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ executablePath: EXE });
  const context = await browser.newContext();
  const page = await context.newPage();

  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.waitForSelector("#signin-email", { timeout: 20000 });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  // ⚠ **WAIT FOR THE ADDRESS TO LEAVE `/signin`, NOT FOR A TIMER.** A fixed
  // sleep signed the first run in "successfully" onto a *Session expired*
  // card, and every check below then measured a screen that was not the
  // statement — which is law 7's *looking at the wrong thing*, at the very
  // top of a walkthrough, where it poisons everything under it.
  await page
    .waitForURL((url) => !url.toString().includes("/signin"), { timeout: 25000 })
    .catch(() => null);
  await page.waitForTimeout(1500);
  note(`signed in as ${EMAIL}; landed on ${page.url()}`);
  if (page.url().includes("/signin")) {
    note("STOP — sign-in did not land. NOTHING below was measured.");
    writeFileSync(`${OUT}/00-README.txt`, notes.join("\n") + "\n");
    await browser.close();
    process.exit(2);
  }

  if (!ACCOUNT) {
    note(
      "STOP — REP_ACCOUNT is unset, so there is no subject to open and NOTHING " +
        "below was measured. That is stated rather than skipped.",
    );
    writeFileSync(`${OUT}/00-README.txt`, notes.join("\n") + "\n");
    await browser.close();
    process.exit(2);
  }

  const url =
    `${BASE}/${TENANT}/reports/statement` +
    `?subject_id=${ACCOUNT}&f.from=2000-01-01&f.to=2099-12-31`;

  // ── 1 · READING the statement ──────────────────────────────────────────
  await page.goto(url, { waitUntil: "networkidle" });
  // ⚠ **WAIT FOR A HEADER CELL, NOT FOR A TIMER.** The first run counted ZERO
  // columns here and SEVEN after the click, and read that as the editor ADDING
  // columns — when the truth was that the table had simply not rendered yet.
  // A count taken before the thing being counted exists is law 7's *looking at
  // the wrong thing*, and it fails in the direction that looks like a finding.
  await page.waitForSelector("table thead th", { timeout: 20000 }).catch(() => null);
  await page.waitForTimeout(1200);
  const reading = await headers(page);
  note(`READING  headers (${reading.length}): ${JSON.stringify(reading)}`);
  verdict(reading.length === 7, `a statement is SEVEN columns; read ${reading.length}`);

  // ── 2 · DEF-REP-7052 · the head ────────────────────────────────────────
  const head = await page
    .locator("[data-report-head]")
    .first()
    .textContent()
    .catch(() => null);
  note(`HEAD: ${head === null ? "NOT PRESENT" : JSON.stringify(head)}`);
  verdict(head !== null && head.trim() !== "", "the statement names the account it is about");
  const body = await page.locator("body").textContent();
  verdict(!body.includes(ACCOUNT), `B14 rule 31 — the account id is NOT on screen`);

  // ── 3 · DEF-REP-7053 · the Download control ────────────────────────────
  const download = page.locator('button[aria-label*="Download" i], button:has-text("Download")');
  const drawn = (await download.count()) > 0;
  verdict(drawn, "a Download control is drawn on the statement");
  await shot(page, "01-statement-reading", 1440);
  await shot(page, "01-statement-reading", 1280);

  // ── 4 · DEF-REP-7072 · press Edit and count again ──────────────────────
  const edit = page.locator('button:has-text("Edit")').first();
  if ((await edit.count()) === 0) {
    note("STOP — no Edit button found, so the column journey was NOT measured.");
    failures += 1;
  } else {
    await edit.click();
    // ⚠ WAIT FOR THE PANEL, not for a timer. Counting headers over a panel
    // that has not opened is the *looking at the wrong thing* shape.
    await page.waitForSelector("text=Attributes", { timeout: 15000 }).catch(() => null);
    await page.waitForTimeout(2000);
    const editing = await headers(page);
    note(`EDITING  headers (${editing.length}): ${JSON.stringify(editing)}`);
    verdict(
      editing.length === reading.length,
      `opening the editor must not change the table: ${reading.length} -> ${editing.length}`,
    );
    // ⚠ **THE SECTION'S OWN COUNT, NOT EVERY BOX ON THE PAGE.** The table
    // draws its own row-select boxes; counting all of them measured 16 and
    // would have failed for reasons that have nothing to do with this defect.
    const offered = await page
      .locator("text=/^\\d+ of \\d+$/")
      .first()
      .textContent()
      .catch(() => null);
    note(`EDITOR   Attributes count reads: ${JSON.stringify(offered)}`);
    verdict(
      offered === "7 of 7",
      `the editor offers the SEVEN this report serves; the section reads ${JSON.stringify(offered)} ` +
        `(it read "7 of 5" before DEF-REP-7070 and offered the dataset's five)`,
    );
    await shot(page, "02-statement-editing", 1440);
    await shot(page, "02-statement-editing", 1280);
    await page.goto(url, { waitUntil: "networkidle" });
    await page.waitForTimeout(1200);
  }

  // ── 5 · THE DOWNLOAD, OVER HTTP, AGAINST A REAL FILE ───────────────────
  if (!drawn) {
    note("STOP — no Download control, so no file was fetched. Stated, not skipped.");
  } else {
    // ⚠ **THE JOB ID COMES OUT OF THE BUTTON'S OWN RESPONSE.** There is no job
    // LIST endpoint, and re-POSTing here would prove a file that the CONTROL
    // did not produce — which is the one thing this check exists to establish.
    const [accepted] = await Promise.all([
      page.waitForResponse(
        (answer) =>
          answer.url().includes("/exports") && answer.request().method() === "POST",
        { timeout: 20000 },
      ),
      download.first().click(),
    ]);
    note(`POST /exports -> ${accepted.status()}`);
    verdict(accepted.status() === 202, "the Download button is accepted, not 404'd");
    const acceptedBody = await accepted.json().catch(() => ({}));
    note(`ACCEPTED: ${JSON.stringify(acceptedBody).slice(0, 300)}`);
    const jobId =
      acceptedBody?.job_id ?? acceptedBody?.id ?? acceptedBody?.data?.job_id ?? null;
    if (jobId === null) {
      note("STOP — the accept carried no job id, so the FILE was not fetched.");
      failures += 1;
    } else {
      let file = { status: 0, headers: {}, bytes: 0, head: "" };
      for (let attempt = 0; attempt < 30; attempt += 1) {
        file = await page.evaluate(async (id) => {
          const answer = await fetch(`/api/exports/${id}/file`, { credentials: "same-origin" });
          const text = answer.ok ? await answer.text() : "";
          const out = {};
          answer.headers.forEach((value, name) => {
            out[name] = value;
          });
          return { status: answer.status, headers: out, bytes: text.length, head: text.slice(0, 500) };
        }, jobId);
        if (file.status === 200) break;
        await page.waitForTimeout(1500);
      }
      note(`FILE status : ${file.status}`);
      note(`FILE headers: ${JSON.stringify(file.headers)}`);
      note(`FILE bytes  : ${file.bytes}`);
      note(`FILE head   :\n${file.head}`);
      verdict(file.status === 200, `GET /api/exports/{job}/file answers 200`);
      verdict(file.bytes > 0, "the file has bytes in it");
      const firstLine = (file.head.split("\n")[0] ?? "").trim();
      verdict(
        firstLine.startsWith("entry_date"),
        `the header row is the statement's own columns; got ${JSON.stringify(firstLine)}`,
      );
      // ⚠ **HARD RULE 2 ON THE WIRE, NOT ONLY ON THE SCREEN.** A sibling
      // shipped `659.780000` in a file because the screen rounded to two and
      // every test passed. This reads the file.
      const money = [...file.head.matchAll(/\d+\.(\d+)/g)].map((m) => m[1].length);
      note(`FILE money decimal places seen: ${JSON.stringify([...new Set(money)])}`);
      verdict(
        money.every((places) => places <= 2),
        "hard rule 2 — money DISPLAYS at 2 decimals, in the file as on the screen",
      );
    }
  }

  // ── 6 · THE UNIT SUBJECT — nine columns and hard rule 8's two-part head ──
  //
  // ⚠ **THE HEAD IS THE BUILDING'S ADDRESS PLUS THE UNIT'S LABEL AND THERE IS
  // NO `unit_address`.** Hard rule 8: a unit refines a premises by LABEL and
  // declares no address of its own. The brief states it on p71 in those words.
  const UNIT = process.env.REP_UNIT ?? "";
  if (UNIT === "") {
    note("STOP — REP_UNIT is unset, so the unit subject was NOT walked. Stated, not skipped.");
  } else {
    const unitUrl =
      `${BASE}/${TENANT}/reports/statement` +
      `?subject=unit&subject_id=${UNIT}&f.from=2000-01-01&f.to=2099-12-31`;
    await page.goto(unitUrl, { waitUntil: "networkidle" });
    await page.waitForSelector("table thead th", { timeout: 20000 }).catch(() => null);
    await page.waitForTimeout(1200);
    const unitHeaders = await headers(page);
    note(`UNIT     headers (${unitHeaders.length}): ${JSON.stringify(unitHeaders)}`);
    verdict(
      unitHeaders.length === 9,
      `the unit statement is NINE columns — Occupant and Account appear here and nowhere else; read ${unitHeaders.length}`,
    );
    const unitHead = await page
      .locator("[data-report-head]")
      .first()
      .textContent()
      .catch(() => null);
    note(`UNIT HEAD: ${unitHead === null ? "NOT PRESENT" : JSON.stringify(unitHead)}`);
    verdict(
      unitHead !== null && unitHead.includes("·"),
      "hard rule 8 — the BUILDING's address and the unit's LABEL, two parts",
    );
    const unitBody = await page.locator("body").textContent();
    verdict(!unitBody.includes(UNIT), "B14 rule 31 — the unit id is NOT on screen");
    await shot(page, "03-unit-statement", 1440);
    await shot(page, "03-unit-statement", 1280);
  }

  note("");
  note(`RESULT: ${failures === 0 ? "ALL CHECKS PASSED" : `${failures} CHECK(S) FAILED`}`);
  writeFileSync(`${OUT}/00-README.txt`, notes.join("\n") + "\n");
  await browser.close();
  process.exit(failures === 0 ? 0 : 1);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
