/**
 * RENDERED-OUTPUT CHECK — `US-RBS-042`, runbook 36 (*Month-end journal file*)
 * on `RBS-006`, in a real browser, plus the FILE, opened and parsed.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: *"no gate looks at rendered output"*,
 * and nine defects were found by that and by nothing else. And the Product
 * Owner's own definition of done, 2026-09-06: *"everything should be executed
 * based on actual code, and rules that we place, also ensure you do web
 * walkthorugh before you sign off the user story or build"*.
 *
 * ⚠ **WHAT IT CANNOT DO, SAID FIRST AND NOT QUIETLY SUBSTITUTED: IT CANNOT
 * FETCH THE FILE OVER HTTP, BECAUSE NO ADDRESS SERVES IT (`DEF-RBS-4312`).**
 * The only download addresses this module mounts are
 * `runbooks/runs/{id}/results/{done|not-done}.csv`, whose nine columns are the
 * RECORD columns — *Subject · Subject type · Planned · Outcome · Amount ·
 * Currency · Decided by · Reason · Fix* — carrying no date and no account code,
 * so a general journal cannot be expressed in them; and the route's `re_path`
 * alternation makes a third file name a deliberate 404. So the file is composed
 * by `rbs_accounting_seed_run.py` from the SAME `journal_csv()` call a future
 * route will make, on the same books, and **this check opens THAT file and
 * parses it**. What is missing is the door, not the file, and pretending
 * otherwise would be a walkthrough that passes over a feature nobody has built.
 *
 * ── HOW TO RUN IT ────────────────────────────────────────────────────────
 *   DJANGO_SETTINGS_MODULE=config.settings.local \
 *   DATABASE_URL="postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub" \
 *     python3.12 10-scripts/render-checks/rbs_accounting_seed_run.py \
 *       --tenant brazosbend --out /tmp/rbs-accounting
 *   # → prints the run id and the CSV's path
 *
 *   SMOKE_SKIP_SEED=1 SMOKE_API_PORT=8091 SMOKE_WEB_PORT=8092 \
 *     ./10-scripts/11-smoke-stack.sh          # or boot the two halves by hand
 *
 *   SMOKE_BASE=http://127.0.0.1:8092 SMOKE_RUN_ID=<the run's id> \
 *   SMOKE_CSV=/tmp/rbs-accounting/journal-2026-07-to-2026-09-USD.csv \
 *   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/rbs-accounting-export.mjs
 *
 * ── WHAT IT ASSERTS ──────────────────────────────────────────────────────
 *   THE FILE (opened and parsed, never grepped)
 *     1  the header row is the Product Owner's SIX columns in their order;
 *     2  every debit and credit cell carries EXACTLY two decimals (hard rule 2
 *        — money is stored to four and DISPLAYS two, and a file is a display
 *        surface). Asserted per cell, not on a total, because one four-decimal
 *        cell in twenty-five is what a total hides;
 *     3  the two columns FOOT — debits equal credits (hard rule 5). Asserted as
 *        a FIGURE, because `assert total` passes on the wrong number;
 *     4  every account code in the file is a code the file also names — no
 *        blank cell, no invented one (decision 3).
 *   THE SCREEN
 *     5  the verdict block's own sentence reaches the head — `DEF-RBS-4284` is
 *        the engine and the renderer agreeing on a NAME and disagreeing on the
 *        payload, with both suites green. ⚠ Its **word** does NOT reach the
 *        screen and this check says so by name (`DEF-RBS-4313`): a leading
 *        verdict is hoisted into the head as its sub-line and only `count` is
 *        used, so *Ready to import* and *No file* are both invisible. The check
 *        asserts the state AS IT IS and flips when the defect is fixed, because
 *        a check that stopped looking would let that day pass unnoticed;
 *     6  the KPI strip drew its three tiles with the RUN's numbers, not zeroes;
 *     7  the records table drew the blocked row and its fix route is a REAL
 *        destination that resolves — asserted by ADDRESS, never as a present
 *        string, because `//host/…` reads as a perfectly good href;
 *     8  the Downloads control is drawn (the block is in the report);
 *     9  B14 rules 31 and 32 — no database id and no rule id in what a clerk
 *        reads, over the whole page AND over every cell of the file;
 *    10  the page does not scroll sideways at 1440.
 */
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:8092";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const RUN_ID = process.env.SMOKE_RUN_ID ?? "";
const CSV = process.env.SMOKE_CSV ?? "";
const KEY = process.env.SMOKE_RUNBOOK ?? "accounting_export";
const OUT = process.env.SMOKE_OUT ?? "/tmp/rbs-accounting-check";
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

if (RUN_ID === "" || CSV === "") {
  console.error(
    "⛔ SMOKE_RUN_ID and SMOKE_CSV are both required.\n" +
      "   This check reads a STORED run and an ALREADY-COMPOSED file; it cannot start\n" +
      "   a run (POST /runbooks/{key}/runs is task L) and it cannot download the file\n" +
      "   (no address serves a six-column journal — DEF-RBS-4312). Run\n" +
      "   rbs_accounting_seed_run.py first; it prints both values.",
  );
  process.exit(2);
}

// ── PART ONE · THE FILE, OPENED AND PARSED ───────────────────────────────
console.log("── the file ──────────────────────────────────────────────");

/** A CSV reader, because splitting on commas is not reading a CSV: a
 *  description like "Tax payable — Local · Bexar County" is one cell and an
 *  account name with a comma in it would silently shift every column right. */
function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = "";
  let quoted = false;
  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') {
        cell += '"';
        i += 1;
      } else if (ch === '"') quoted = false;
      else cell += ch;
      continue;
    }
    if (ch === '"') quoted = true;
    else if (ch === ",") {
      row.push(cell);
      cell = "";
    } else if (ch === "\n") {
      row.push(cell);
      rows.push(row);
      row = [];
      cell = "";
    } else if (ch !== "\r") cell += ch;
  }
  if (cell !== "" || row.length > 0) {
    row.push(cell);
    rows.push(row);
  }
  return rows;
}

const csvText = readFileSync(CSV, "utf8");
const rows = parseCsv(csvText);
const header = rows[0] ?? [];
const body = rows.slice(1).filter((r) => r.length === 6);

check(
  JSON.stringify(header) ===
    JSON.stringify(["date", "account code", "description", "debit", "credit", "reference"]),
  `the header is the Product Owner's six columns in order — saw [${header.join(", ")}]`,
);
check(body.length > 0, `the file carries rows (${body.length}); a header alone is not a file`);

let twoDecimals = true;
let codesPresent = true;
let debits = 0n;
let credits = 0n;
/** Money as integer cents, so the footing is exact — a float sum of 25 cells
 *  can be a cent out and would make this check disagree with the product for
 *  reasons that have nothing to do with the product (hard rule 2: never float). */
function cents(text) {
  const m = /^(-?)(\d+)\.(\d{2})$/.exec(text);
  if (m === null) return null;
  const value = BigInt(m[2]) * 100n + BigInt(m[3]);
  return m[1] === "-" ? -value : value;
}
for (const [index, row] of body.entries()) {
  const [when, code, , debit, credit, reference] = row;
  const d = cents(debit);
  const c = cents(credit);
  if (d === null || c === null) {
    twoDecimals = false;
    console.log(`      row ${index + 2}: debit=${debit} credit=${credit} is not 2dp`);
  } else {
    debits += d;
    credits += c;
  }
  if (!code || !code.trim()) {
    codesPresent = false;
    console.log(`      row ${index + 2}: the account code cell is EMPTY`);
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(when)) {
    check(false, `row ${index + 2}: the date cell is not a date — "${when}"`);
  }
  if (!/^\d{4}-\d{2}$/.test(reference)) {
    check(false, `row ${index + 2}: the reference cell is not a month — "${reference}"`);
  }
}
check(twoDecimals, "every debit and credit cell carries exactly two decimals (hard rule 2)");
check(codesPresent, "every row names an account code — none blank, none invented (decision 3)");
check(
  debits === credits,
  `the file BALANCES — debits ${Number(debits) / 100} = credits ${Number(credits) / 100} (hard rule 5)`,
);
for (const pattern of FORBIDDEN_IN_CLERK_COPY) {
  const hit = csvText.match(pattern);
  check(hit === null, `no internal id in the file${hit ? ` — saw ${hit[0]}` : ""}`);
}

// ── PART TWO · THE SCREEN ────────────────────────────────────────────────
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
    if (!/\/runbooks\//.test(response.url())) return;
    try {
      wire.push({ url: response.url(), body: await response.text() });
    } catch {
      /* a redirect or a bodyless response has nothing to read */
    }
  });

  console.log("── sign in ───────────────────────────────────────────────");
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  // ⚠ `input[type="email"]` MATCHES NOTHING ON THIS SCREEN — `S3` draws the
  // work-email field as `type="text"` with `id="signin-email"`.
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  // ⚠ WAIT FOR THE LANDING, NOT FOR THE NETWORK. Sign-in is an XHR, so the page
  // never navigates and `networkidle` returns before the session cookie exists —
  // every later call then 401s and reads as a broken screen.
  await page.waitForURL(/\/dashboard(\?|$)/, { timeout: 30000 });

  console.log("── RBS-006 · the month-end journal file ──────────────────");
  await page.goto(`${BASE}/${TENANT}/runbooks/${KEY}/runs/${RUN_ID}`, {
    waitUntil: "networkidle",
  });
  // ⚠ **WAIT FOR A BLOCK TO EXIST BEFORE READING THE TEXT, AND THE FIRST DRAFT
  // DID NOT.** `networkidle` returns when the network is quiet, which on this
  // screen is BEFORE React has drawn the report: the run header arrives, the
  // report arrives, and the blocks render a tick later. A `textContent("body")`
  // taken at that moment is a snapshot of an empty result region, so the
  // verdict word, all three KPI labels and all four column headings read as
  // MISSING — nine failures over a screen that was drawing them correctly a
  // few milliseconds later, which the `[data-block="downloads"]` query (run
  // afterwards, against the live DOM) found without trouble. A check that
  // reports a product failure for a fault in the check is worse than no check
  // (hard-won law 7's *looking at the wrong thing*).
  await page.waitForSelector('[data-block="records"]', { timeout: 30000 });
  await page.screenshot({ path: join(OUT, "rbs-006-accounting.png"), fullPage: true });
  const pageText = (await page.textContent("body")) ?? "";

  // ⚠ **ASK THE SERVER DIRECTLY RATHER THAN SIFTING THE RESPONSE STREAM.** A
  // first draft read the report out of `page.on("response")`, and the handler's
  // `await response.text()` had not resolved by the time the checks ran — so
  // `served` was null and the check printed *"the server served no blocks"*
  // over a request the backend log shows answering **200 with 3,514 bytes**.
  // That is a check reporting a product failure for a fault in the check, which
  // is worse than no check at all (hard-won law 7's *looking at the wrong
  // thing*). This fetch runs INSIDE the page, so it carries the same session
  // and the same origin the screen used, and it either has an answer or fails
  // loudly.
  const served = await page.evaluate(async ({ tenant, runId }) => {
    const response = await fetch(`/api/${tenant}/runbooks/runs/${runId}/report`, {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    });
    if (!response.ok) return { error: `${response.status} ${response.statusText}` };
    return response.json();
  }, { tenant: TENANT, runId: RUN_ID });
  check(
    served !== null && served.error === undefined,
    `the report endpoint answered${served?.error ? ` — ${served.error}` : ""}`,
  );
  const blockNames = (served?.blocks ?? []).map((b) => b.block);
  check(
    JSON.stringify(blockNames) === JSON.stringify(["verdict", "kpis", "records", "downloads"]),
    `the server served four of the twelve blocks — saw [${blockNames.join(", ")}]`,
  );

  const verdict = served?.blocks?.find((b) => b.block === "verdict") ?? null;
  check(verdict !== null, "the server served a verdict block");
  if (verdict !== null) {
    check(
      pageText.includes(verdict.payload.count),
      `the head says what the run found: "${verdict.payload.count}"`,
    );
    // ⚠ **THE VERDICT'S *WORD* DOES NOT REACH THE SCREEN, AND THAT IS
    // `DEF-RBS-4313` RATHER THAN A LOOSE ASSERTION.** `RunResult.tsx` hoists a
    // LEADING verdict block into the page head as its sub-line and uses only
    // `count` — `word`, `tone` and `detail` are dropped, so a clerk reads
    // *"1 to fix · 3 months open."* and never learns whether the word beside it
    // is **Ready to import** or **No file**. That is every runbook's problem,
    // not this one's, and the frontend belongs to another lane. **So this
    // asserts the state as it IS and names the defect** — a check that quietly
    // stopped looking would let the day it is fixed pass unnoticed, and a check
    // that failed here would report a product defect as this runbook's.
    const bandDrawn = (await page.$("[data-verdict-word]")) !== null;
    check(
      !bandDrawn === !pageText.includes(verdict.payload.word),
      bandDrawn
        ? `the verdict word reached the screen: "${verdict.payload.word}" — DEF-RBS-4313 is FIXED, `
          + "delete this branch and assert the word plainly"
        : `the verdict word is DROPPED by the head (DEF-RBS-4313): "${verdict.payload.word}" `
          + "is served and never drawn",
    );
  }

  const kpis = served?.blocks?.find((b) => b.block === "kpis") ?? null;
  if (kpis !== null) {
    for (const tile of kpis.payload.tiles) {
      check(pageText.includes(tile.label), `KPI tile "${tile.label}" drew`);
    }
    const total = kpis.payload.tiles.find((t) => t.id === "total");
    check(
      total !== undefined && total.value.kind === "money" && total.value.currency.length === 3,
      "the file total is money and carries a CHAR(3) currency (hard rule 2)",
    );
    // The screen's figure must be the FILE's figure. Two answers to *what did
    // this month hold* is the failure `apps/ledger/exports.py` names.
    check(
      total !== undefined && cents(total.value.amount) === debits,
      `the tile and the file agree on the total (tile ${total?.value.amount}, file ${Number(debits) / 100})`,
    );
  }

  const records = served?.blocks?.find((b) => b.block === "records") ?? null;
  if (records !== null) {
    for (const column of records.payload.columns) {
      check(pageText.includes(column.label), `column "${column.label}" drew`);
    }
    check(
      records.payload.rows.length > 0,
      `the blocked list has real content (${records.payload.rows.length} row(s))`,
    );
    for (const row of records.payload.rows) {
      const fix = row.cells.fix;
      const link = await page.$(`a[href$="${fix.to}"]`);
      check(link !== null, `fix route "${fix.label}" is a real link to /${fix.to}`);
    }
  }

  const downloads = served?.blocks?.find((b) => b.block === "downloads") ?? null;
  check(downloads !== null, "the server served a downloads block");
  if (downloads !== null && downloads.payload.files.length > 0) {
    check(
      (await page.$('[data-block="downloads"]')) !== null,
      "the Downloads control is drawn on the screen",
    );
  }

  for (const pattern of FORBIDDEN_IN_CLERK_COPY) {
    const hit = pageText.match(pattern);
    check(hit === null, `no internal id on screen${hit ? ` — saw ${hit[0]}` : ""}`);
  }
  check((await page.evaluate(SIDEWAYS)) === 0, "the result page does not scroll sideways at 1440");

  writeFileSync(join(OUT, "wire.json"), JSON.stringify(wire, null, 2));
  await browser.close();

  console.log("");
  if (failures.length > 0) {
    console.error(`⛔ ${failures.length} check(s) failed:`);
    for (const l of failures) console.error(`   · ${l}`);
    process.exit(1);
  }
  console.log(`✓ every check passed — screenshots and the wire capture in ${OUT}`);
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
