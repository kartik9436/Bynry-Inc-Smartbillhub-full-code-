#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:   CR-053 task 13 — *"Print bills"* (W4). PO ruling 2026-08-30:
//           *"Im okay with this"* on the PDF-set-plus-manifest recommendation.
// Screens:  Print bills (`/{tenant}/billing/print`) · S30 (the Billing header
//           link that reaches it)
// Rules:    BR-NOT-029 (the pair; the fourteen manifest columns; (b) an
//           incomplete address is REPORTED and held; (c) no CASS / NCOA /
//           barcode claim) · BR-CUS-674 (an address is read, never written) ·
//           BR-BIL-026 (the PINNED template renders the page) · B14 rule 31
//           (no database id is the visible value of a field) · hard-won law 6
//           (diff the RUNNING app — no gate in this repo reads rendered output)
// Defects:  DEF-2703 · DEF-2847 · DEF-2848
// ───────────────────────────────────────────────────────
/**
 * Trigger a REAL print set from the REAL screen, download it, and open it.
 *
 * ⚠ **WHY THIS EXISTS BESIDE 37 PASSING TEST CASES.** The Product Owner's rule
 * of 2026-08-30: *"All UI screen should be confirm using real broswer testing
 * and not just based on test cases"*. And it is not ceremony here — the whole of
 * task 13 is a promise about a FILE, and **jsdom downloads nothing, opens no
 * archive and counts no PDF.** A screen can hold thirty green cases asserting
 * that a job was polled and hand a clerk an empty zip.
 *
 * ⚠ **AND THE ASSERTIONS ARE WRITTEN SO THEY CAN FAIL.** Seven checks that
 * could not fail were found in this repository in one day, so:
 *   · every count is asserted **> 0** as well as equal, because `0 === 0` is
 *     what a set that held every bill produces and `DEF-2703` makes holding
 *     everything the DEFAULT on a tenant seeded from service requests;
 *   · a manifest row is matched to its bill **by the bill number**, and its
 *     account number, customer name, amount and dates are compared against
 *     `GET /invoices/{id}` fetched in the same run — a set that wrote every row
 *     from the first bill would pass a positional check;
 *   · the PDF named by that row is **opened**, and its own page count is read
 *     out of its bytes and compared with the number the manifest claims.
 *
 * ── HOW TO RUN IT ────────────────────────────────────────────────────────
 *   createdb sbh_cr053w4
 *   DATABASE_URL=…/sbh_cr053w4 python3 06-backend/manage.py migrate
 *   DATABASE_URL=…/sbh_cr053w4 python3 06-backend/manage.py seed_demo
 *   DATABASE_URL=…/sbh_cr053w4 python3 06-backend/manage.py load_sample_data \
 *       --tenant brazosbend
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local DATABASE_URL=…/sbh_cr053w4 \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8053 --noreload &
 *   (cd 07-frontend && npx vite build && \
 *      PORT=4253 API_PROXY_TARGET=http://127.0.0.1:8053 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4253 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr053-print-bills.mjs
 *
 * ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** The development
 * database is shared by every lane; a reseed mid-run looks exactly like a broken
 * screen from in here, and on 2026-08-30 that cost the CR-053 lane nine phantom
 * failures.
 *
 * ⚠ **A TENANT SEEDED BEFORE `DEF-2848` HOLDS EVERY BILL, CORRECTLY.** Its
 * mailing addresses have a town and a postcode and no STATE, so `BR-NOT-029`
 * clause (b) refuses all of them — the rule working, not the build failing.
 * This check REPORTS that as `⊘ not exercised` rather than passing quietly; to
 * exercise the happy path, seed after the fixture fix or fill the state in.
 */
import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { execFileSync } from "node:child_process";
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4253";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr053-print-bills";
const VIEWPORT = { width: 1440, height: 1000 };

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

/** Something this run could NOT exercise, said out loud. A silent skip is the
 *  shape of a check that cannot fail. */
const notes = [];
function note(message) {
  console.log(`   ⊘ ${message}`);
  notes.push(message);
}

const SIDEWAYS = `Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)`;

/** The Print bills screen, as a browser sees it. */
const READ_PRINT_SCREEN = `(() => {
  const y = (el) => (el ? Math.round(el.getBoundingClientRect().y) : null);
  const text = (el) => (el ? (el.innerText || "").replace(/\\s+/g, " ").trim() : null);
  const scope = document.querySelector('[data-print-scope]');
  const summary = document.querySelector('[data-print-summary]');
  const notesPanel = document.querySelector('[data-print-notes]');
  const rollup = document.querySelector('[data-print-rollup]');
  const buttons = [...document.querySelectorAll("button")];
  const build = buttons.find((b) => (b.textContent || "").trim() === "Build the print set");
  return {
    title: text(document.querySelector("h1")),
    scopePresent: scope !== null,
    scopeOptions: scope ? [...scope.querySelectorAll("option")].map((o) => o.textContent.trim()) : [],
    rollupText: text(rollup),
    summaryText: text(summary),
    notesText: text(notesPanel),
    summaryY: y(summary),
    notesY: y(notesPanel),
    buildPresent: build !== undefined,
    buildDisabled: build ? build.disabled : null,
    buildReason: build ? build.getAttribute("title") : null,
    sideways: ${SIDEWAYS},
    // Everything a person can READ on this page, filtered to the lines carrying
    // a uuid. innerText is the point: it is what a clerk sees (B14 rule 31).
    uuidLinesOnPage: (document.body.innerText || "")
      .split("\\n")
      .map((one) => one.trim())
      .filter((one) => /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i.test(one)),
  };
})()`;

const READ_OUTCOME = `(() => {
  const out = document.querySelector('[data-print-outcome]');
  const link = out ? out.querySelector("a") : null;
  return {
    state: out ? out.getAttribute("data-print-outcome") : null,
    text: out ? (out.innerText || "").replace(/\\s+/g, " ").trim() : null,
    href: link ? link.getAttribute("href") : null,
  };
})()`;

/** One CSV, parsed. Deliberately simple: the writer quotes with Python's own
 *  `csv` module and every field this file reads is plain. */
function parseCsv(body) {
  const rows = [];
  let row = [];
  let field = "";
  let quoted = false;
  for (let i = 0; i < body.length; i += 1) {
    const ch = body[i];
    if (quoted) {
      if (ch === '"' && body[i + 1] === '"') {
        field += '"';
        i += 1;
      } else if (ch === '"') {
        quoted = false;
      } else {
        field += ch;
      }
    } else if (ch === '"') {
      quoted = true;
    } else if (ch === ",") {
      row.push(field);
      field = "";
    } else if (ch === "\n") {
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else if (ch !== "\r") {
      field += ch;
    }
  }
  if (field !== "" || row.length > 0) {
    row.push(field);
    rows.push(row);
  }
  return rows.filter((one) => one.length > 1 || one[0] !== "");
}

/** How many pages this PDF has, read out of its own bytes — the SAME question
 *  `apps/billing/print_set.page_count_of` answers server-side, asked here
 *  independently so the two can disagree. */
function pageCountOf(buffer) {
  const text = buffer.toString("latin1");
  const declared = /\/Type\s*\/Pages\b[^>]*?\/Count\s+(\d+)/.exec(text);
  if (declared) return Number(declared[1]);
  const objects = text.match(/\/Type\s*\/Page(?![s])/g);
  return objects ? objects.length : 0;
}

async function main() {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({
    viewport: VIEWPORT,
    acceptDownloads: true,
  });
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });

  console.log(`cr053 task 13: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);

  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });
  console.log("   signed in");

  // ── 1 · THE SCREEN IS REACHABLE FROM THE PRODUCT ────────────────────────
  // Hard-won law 2: a route registered and linked from nowhere is a feature
  // that does not exist. Reached by CLICKING, never by typing the URL.
  console.log("\n── 1 · reached from the Billing header ──");
  await page.goto(`${BASE}/${TENANT}/billing`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  const printLink = await page.evaluate(`(() => {
    const a = [...document.querySelectorAll("a")].find(
      (one) => (one.textContent || "").trim() === "Print bills",
    );
    return a ? a.getAttribute("href") : null;
  })()`);
  check(printLink !== null, `the Billing header carries a Print bills link (href=${printLink})`);
  if (printLink !== null) {
    await page.click('a:text-is("Print bills")');
    await page.waitForURL((u) => u.pathname.endsWith("/billing/print"), { timeout: 20000 });
    check(true, "clicking it ARRIVES at the Print bills screen");
  } else {
    await page.goto(`${BASE}/${TENANT}/billing/print`, { waitUntil: "networkidle" });
  }
  await page.waitForTimeout(2000);
  await page.screenshot({ path: join(OUT, "print-bills.png"), fullPage: true });

  const screen = await page.evaluate(READ_PRINT_SCREEN);
  check(screen.title === "Print bills", `the page is titled "${screen.title}"`);
  check(screen.scopePresent, "the scope control is on the screen");
  check(
    screen.scopeOptions.length > 0 && screen.scopeOptions[0] === "Every issued bill",
    `the scope offers ${screen.scopeOptions.length} option(s), first "${screen.scopeOptions[0]}"`,
  );
  check(screen.summaryText !== null, "the summary panel drew");
  check(screen.notesText !== null, "the notes panel drew");
  check(
    screen.summaryY !== null && screen.notesY !== null && screen.summaryY < screen.notesY,
    `summary sits above the notes by measured Y (${screen.summaryY} < ${screen.notesY})`,
  );
  check(screen.sideways === 0, `the page does not scroll sideways (${screen.sideways}px)`);
  check(
    screen.uuidLinesOnPage.length === 0,
    `B14 rule 31: no uuid is readable on the page (${screen.uuidLinesOnPage.length} line(s))`,
  );

  // ── 2 · BR-NOT-029 CLAUSE (c) IS ON SCREEN, IN WORDS ────────────────────
  console.log("\n── 2 · the mail standards we do NOT perform ──");
  const notesText = screen.notesText ?? "";
  check(notesText.includes("CASS-certified"), "the screen says the addresses are NOT CASS-certified");
  check(notesText.includes("NCOA-processed"), "it says they are NOT NCOA-processed");
  check(
    notesText.includes("Intelligent Mail barcode"),
    "it says no Intelligent Mail barcode is applied",
  );
  check(
    /not been CASS-certified/i.test(notesText),
    "and it says so as a DENIAL — silence here would read as a claim",
  );

  // ── 3 · THE ROLL-UP IS A REAL COUNT ─────────────────────────────────────
  console.log("\n── 3 · what the screen says it will produce ──");
  console.log(`   rollup: ${screen.rollupText}`);
  console.log(`   summary: ${screen.summaryText}`);
  const counted = /(\d[\d,]*) bills/.exec(screen.rollupText ?? "");
  const billCount = counted ? Number(counted[1].replace(/,/g, "")) : 0;
  check(billCount > 0, `the screen counted ${billCount} bill(s) — and it is greater than zero`);
  check(
    screen.buildPresent && screen.buildDisabled === false,
    `the build control is enabled (reason=${screen.buildReason ?? "none"})`,
  );

  // ── 4 · BUILD IT, FROM THE SCREEN, AND DOWNLOAD WHAT LANDS ──────────────
  console.log("\n── 4 · build the set and download it ──");
  const downloadPromise = page.waitForEvent("download", { timeout: 180000 }).catch(() => null);
  await page.click('button:text-is("Build the print set")');
  await page.waitForFunction(
    `document.querySelector('[data-print-outcome]') !== null`,
    undefined,
    { timeout: 180000 },
  );
  const outcome = await page.evaluate(READ_OUTCOME);
  await page.screenshot({ path: join(OUT, "print-bills-done.png"), fullPage: true });
  check(outcome.state === "ready", `the run finished: "${outcome.text}"`);
  check(outcome.href !== null, `it offers a download (${outcome.href})`);

  let archivePath = null;
  if (outcome.href !== null) {
    // CLICKED, not fetched: the anchor is a same-origin navigation carrying the
    // session cookie, and a link that 404s is exactly what this must catch.
    await page.click('[data-print-outcome] a');
    const download = await downloadPromise;
    if (download === null) {
      check(false, "the download link produced no file");
    } else {
      archivePath = join(OUT, download.suggestedFilename());
      await download.saveAs(archivePath);
      check(true, `the archive downloaded as ${download.suggestedFilename()}`);
      check(
        download.suggestedFilename().endsWith(".zip"),
        "and it is named as an archive, not as a CSV",
      );
    }
  }

  // ── 5 · OPEN IT. COUNT THE PDFs. COUNT THE ROWS. ────────────────────────
  if (archivePath !== null) {
    console.log("\n── 5 · open the archive ──");
    const listing = execFileSync("unzip", ["-Z1", archivePath], { encoding: "utf8" })
      .split("\n")
      .map((one) => one.trim())
      .filter(Boolean);
    const pdfs = listing.filter((one) => one.startsWith("bills/") && one.endsWith(".pdf"));
    check(listing.includes("manifest.csv"), "manifest.csv is in the archive");
    check(listing.includes("held-back.csv"), "held-back.csv is in the archive");
    check(listing.includes("README.txt"), "README.txt is in the archive");
    check(pdfs.length > 0, `it holds ${pdfs.length} PDF(s) — and it is greater than zero`);

    const manifestCsv = execFileSync("unzip", ["-p", archivePath, "manifest.csv"], {
      encoding: "utf8",
    });
    const heldCsv = execFileSync("unzip", ["-p", archivePath, "held-back.csv"], {
      encoding: "utf8",
    });
    const readme = execFileSync("unzip", ["-p", archivePath, "README.txt"], { encoding: "utf8" });
    const manifest = parseCsv(manifestCsv);
    const held = parseCsv(heldCsv);
    const header = manifest[0];
    const rows = manifest.slice(1);

    check(
      header.join(",") ===
        "account_no,bill_no,customer_name,address_line_1,address_line_2,city,state," +
          "postal_code,country,page_count,bill_date,due_date,amount_due,pdf_filename",
      `the manifest carries BR-NOT-029's fourteen columns in the ruled order (${header.length})`,
    );
    check(rows.length > 0, `it holds ${rows.length} row(s) — and it is greater than zero`);
    check(
      rows.length === pdfs.length,
      `one PDF per bill: ${pdfs.length} PDF(s) == ${rows.length} manifest row(s)`,
    );
    console.log(`   held back: ${held.length - 1} bill(s)`);

    // ── 6 · A ROW, CHECKED AGAINST THE BILL IT NAMES ──────────────────────
    console.log("\n── 6 · one row, checked against its bill ──");
    const idx = (name) => header.indexOf(name);
    const sample = rows[0];
    const billNo = sample[idx("bill_no")];
    console.log(`   checking ${billNo}`);

    // The bill, fetched from the SERVER in the same run. Matched by NUMBER, so
    // a set that wrote every row from one invoice cannot pass.
    const served = await page.evaluate(
      `(async () => {
         const list = await fetch("/api/${TENANT}/invoices?q=" + encodeURIComponent(${JSON.stringify(
           billNo,
         )}) + "&per=5", { credentials: "same-origin" }).then((r) => r.json());
         const row = (list.results || []).find((one) => one.invoice_no === ${JSON.stringify(billNo)});
         if (!row) return null;
         const detail = await fetch("/api/${TENANT}/invoices/" + row.id, {
           credentials: "same-origin",
         }).then((r) => r.json());
         return { row, detail };
       })()`,
    );
    if (served === null) {
      check(false, `the server could not be asked about ${billNo}`);
    } else {
      const bill = served.row;
      check(
        sample[idx("account_no")] === bill.account_no && bill.account_no !== null,
        `account_no matches the bill: ${sample[idx("account_no")]} == ${bill.account_no}`,
      );
      check(
        sample[idx("customer_name")] === bill.customer_name && bill.customer_name !== "",
        `customer_name matches: "${sample[idx("customer_name")]}" == "${bill.customer_name}"`,
      );
      check(
        sample[idx("due_date")] === (bill.due_date ?? ""),
        `due_date matches: ${sample[idx("due_date")]} == ${bill.due_date}`,
      );
      check(
        sample[idx("bill_date")] === (bill.service_date ?? ""),
        `bill_date is the bill's own service date: ${sample[idx("bill_date")]} == ${bill.service_date}`,
      );
      // CLAUDE.md rule 2 — money is STORED to 4dp and DISPLAYS at 2. The
      // vendor's file is a display, and the 6dp stored string must be ABSENT.
      const stored = bill.total ?? "";
      const shown = sample[idx("amount_due")];
      check(
        /^\d+\.\d{2}$/.test(shown),
        `amount_due displays at exactly 2dp: "${shown}" (stored "${stored}")`,
      );
      check(
        Math.abs(Number(shown) - Number(stored)) < 0.005,
        `and it is the bill's own total, rounded once: ${shown} ≈ ${stored}`,
      );
      check(shown !== stored, "the stored precision is NOT what the vendor is handed");
    }

    // ── 7 · THE PDF THAT ROW NAMES, OPENED AND COUNTED ────────────────────
    console.log("\n── 7 · the page the row names ──");
    const named = sample[idx("pdf_filename")];
    check(
      pdfs.includes(`bills/${named}`),
      `the PDF the row names is in the archive (bills/${named})`,
    );
    check(named === `${billNo}.pdf`, `and it is named by the BILL NUMBER, not by an id (${named})`);
    if (pdfs.includes(`bills/${named}`)) {
      const bytes = execFileSync("unzip", ["-p", archivePath, `bills/${named}`], {
        encoding: "buffer",
        maxBuffer: 64 * 1024 * 1024,
      });
      writeFileSync(join(OUT, named), bytes);
      check(
        bytes.slice(0, 5).toString("latin1") === "%PDF-",
        `it really is a PDF (${bytes.length} bytes)`,
      );
      const pages = pageCountOf(bytes);
      check(pages > 0, `it has ${pages} page(s) — and it is greater than zero`);
      check(
        String(pages) === sample[idx("page_count")],
        `the manifest's page_count is the page count the file actually has (${sample[idx("page_count")]})`,
      );
      const inside = bytes.toString("latin1");
      check(inside.includes(billNo), `the page itself carries the bill number ${billNo}`);
    }

    // ── 8 · THE ADDRESS, DISCRETE — AND NEVER CUT OUT OF A BLOB ───────────
    console.log("\n── 8 · the address BR-NOT-029 clause (a) asks for ──");
    check(sample[idx("address_line_1")] !== "", `address line 1 is filled ("${sample[idx("address_line_1")]}")`);
    check(sample[idx("city")] !== "", `city is filled ("${sample[idx("city")]}")`);
    check(sample[idx("state")] !== "", `state is filled ("${sample[idx("state")]}")`);
    check(sample[idx("postal_code")] !== "", `postal code is filled ("${sample[idx("postal_code")]}")`);
    // DEF-2847: two ruled columns with no schema behind them. EMPTY, and the
    // thing they must never be is a slice of line 1.
    check(
      sample[idx("address_line_2")] === "",
      "address line 2 is empty and was NOT carved out of line 1",
    );
    check(sample[idx("country")] === "", "country is empty and was NOT taken from the tenant's own");
    check(
      rows.every((one) => one[idx("city")] !== "" && one[idx("state")] !== "" && one[idx("postal_code")] !== ""),
      `clause (b): every one of the ${rows.length} rows in the file has all three mandatory parts`,
    );

    // ── 9 · WHAT WAS HELD, AND WHY, IN WORDS ─────────────────────────────
    console.log("\n── 9 · what was held back ──");
    if (held.length > 1) {
      check(
        held[0].join(",") === "account_no,bill_no,reason_code,reason",
        "held-back.csv carries its four columns",
      );
      check(
        held.slice(1).every((one) => one[3].length > 20),
        `every one of the ${held.length - 1} held bills carries a sentence, not just a code`,
      );
      console.log(`   e.g. ${held[1][1]}: ${held[1][3].slice(0, 120)}`);
    } else {
      note("no bill was held back in this run, so the held-back report was not exercised");
    }

    // ── 10 · THE README SAYS WHAT WE DID NOT DO ───────────────────────────
    console.log("\n── 10 · the README a vendor reads ──");
    check(readme.includes("NOT been CASS-certified"), "README: not CASS-certified");
    check(readme.includes("NOT been NCOA-processed"), "README: not NCOA-processed");
    check(readme.includes("No Intelligent Mail barcode"), "README: no barcode");
    check(
      readme.includes("only when the account holder tells us"),
      "README: an address changes only when the account holder says so",
    );
    check(
      readme.includes(`PDF files: ${pdfs.length}`),
      `README states the PDF count and it matches the archive (${pdfs.length})`,
    );
    check(
      readme.includes(`Bills in this set: ${rows.length}`),
      `README states the manifest row count and it matches (${rows.length})`,
    );
    check(
      !/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i.test(
        `${manifestCsv}\n${heldCsv}\n${readme}`,
      ),
      "B14 rule 31: no uuid anywhere in the manifest, the held report or the README",
    );
  } else {
    note("no archive was downloaded, so nothing inside one was checked");
  }

  await browser.close();

  console.log(`\n${failures.length === 0 ? "PASS" : "FAIL"}: ${failures.length} failure(s), ${notes.length} not exercised`);
  for (const one of failures) console.log(`   ⛔ ${one}`);
  for (const one of notes) console.log(`   ⊘ ${one}`);
  process.exit(failures.length === 0 ? 0 : 1);
}

main().catch((error) => {
  console.error(error);
  process.exit(2);
});
