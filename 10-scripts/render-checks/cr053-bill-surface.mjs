#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:   CR-053 tasks 1–5, 6, 8 and 10–12 — the bills list and one bill ·
//           CR-052 task 11 — the bill message and ways to pay on the document.
// Screens:  S30 (All bills · bill detail: Document tab, CHARGES TAB, Corrections
//           tab · the bill document)
// Defects:  DEF-2451 (Print bill said the endpoint did not exist; it did) ·
//           DEF-2450 (the Customer's-bill link went to a route that does not
//           exist) · DEF-2453 (rule 15's overflow) · DEF-2452 (rule 16's
//           remembered page size) · DEF-2438 (a plain `text-right` LOSES to
//           PlainTable's descendant variant, so no figure in the kit has ever
//           been right-aligned — read COMPUTED text-align, never the class
//           attribute) · DEF-2429 (a minimum-bill line stores no service, so
//           per-service money sits in the bill-level bucket) · DEF-2428 (the
//           charge code is null today and the id must not be printed instead) ·
//           DEF-2716 (the Accounting code, Rate version and Billing run cells
//           each printed a raw database id, which B14 rule 31 forbade on
//           2026-08-30 — no gate reads rendered output, so this file is the
//           only thing that can see it)
// Rules:    B14 rule 31 (nothing internal is visible to a utility user) ·
//           BR-BIL-036 (print is the floor) · BR-BIL-048 / BR-BIL-064
//           (`is_latest` and the chain head) · BR-SHL-025 (disabled WITH its
//           reason) · B14 rules 12, 15, 16 · hard-won law 6 (diff the RUNNING
//           app — no gate in this repo reads rendered output)
// ───────────────────────────────────────────────────────
/**
 * Open the two S30 surfaces in a REAL browser and read what comes back.
 *
 * ⚠ **WHY THIS EXISTS BESIDE 188 PASSING TEST CASES.** The Product Owner's rule
 * of 2026-08-30: *"All UI screen should be confirm using real broswer testing
 * and not just based on test cases"*. And it is not ceremony here — the whole of
 * task 3 is a promise about a PDF drawn inside an `<iframe>`, and **jsdom
 * renders no iframe content at all**. A screen can hold sixteen green cases
 * asserting the frame's `src` and draw a blank grey box.
 *
 * ⚠ **REBUILD BEFORE MEASURING.** A check pointed at a stale `vite build`
 * reports failure with total confidence and no hint that it is reading the wrong
 * bytes — `cr049-bill-document.mjs` records the day that cost a full
 * investigation.
 *
 * ── HOW TO RUN IT ────────────────────────────────────────────────────────
 *   DJANGO_SETTINGS_MODULE=config.settings.local \
 *   DATABASE_URL="postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub" \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8031 --noreload &
 *   (cd 07-frontend && npx vite build && \
 *      PORT=4231 API_PROXY_TARGET=http://127.0.0.1:8031 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4231 \
 *   SMOKE_BILL=<an ISSUED invoice uuid> \
 *   SMOKE_BILL_SUPERSEDED=<an invoice that has been corrected> \
 *   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr053-bill-surface.mjs
 *
 * ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** The development
 * database is shared by every lane, and on 2026-08-30 this check was run three
 * times against it while a sibling replayed migrations and re-seeded: every
 * invoice id changed under it, the demo login answered 404 for several minutes,
 * and the run reported nine failures that were entirely about the data. **A
 * reseed looks exactly like a broken screen from in here.** The fix is two
 * commands and it is worth them:
 *
 *     createdb smartbillhub_cr052w2          # THIS lane's own, 2026-08-31
 *     createdb smartbillhub_cr053            # the 2026-08-30 lane's
 *     DATABASE_URL=…/smartbillhub_cr053 python3 manage.py migrate
 *     DATABASE_URL=…/smartbillhub_cr053 python3 manage.py seed_demo
 *
 * `seed_demo` alone gives 94 bills, a correction chain and a document store
 * under its own tenant directory — everything this check needs. (`smartbillhub_
 * cr053` was left in place on 2026-08-30 for exactly this reason.)
 *
 * ⚠ **THE DOCUMENT STORE IS ON DISK AND IS NOT IN A WORKTREE.** A backend run
 * from a `git worktree` resolves `DOCUMENT_STORAGE_DIR` to `<worktree>/06-backend
 * /var/documents`, which is empty, and every bill then answers `409
 * billing.document.bytesMissing` — a data fault that reads exactly like a code
 * fault. Point the run at the main checkout's `var/` (a symlink is enough) or
 * the print half of this check cannot pass on any bill.
 *
 * ── WHAT IT ASSERTS ──────────────────────────────────────────────────────
 *   1  PRINT BILL IS A LIVE LINK on an issued bill, and the URL it names really
 *      answers `application/pdf` — fetched, not assumed.
 *   2  THE PRINTABLE PAGE IS ON THE SCREEN: a frame with a non-zero box, and
 *      the browser's own PDF viewer inside it rather than an empty rectangle.
 *   3  THE FIVE PANELS ARE BELOW IT, in their ruled order, top to bottom by
 *      measured Y — which is the half no jsdom test can see.
 *   4  THE CUSTOMER'S-BILL LINK GOES SOMEWHERE: clicked, and the page that
 *      arrives is the bill document and not a 404 (DEF-2450).
 *   5  THE CORRECTIONS TAB SAYS WHETHER THIS BILL IS THE CURRENT ONE, and on a
 *      superseded bill NAMES its replacement.
 *   6  THE BILLS LIST TOOLBAR IS ONE ROW: search, filters, download glyph and
 *      the column chooser, none of them wrapped onto a second line (DEF-1085's
 *      failure mode, which is invisible to every source-level check).
 *   7  ROW ACTIONS ARE ICONS WITH NAMES, at most two per row.
 *   8  THE PAGER IS ON THE TABLE and the page size SURVIVES A RELOAD.
 *   9  NEITHER PAGE SCROLLS SIDEWAYS.
 *  10  THE CHARGES TAB CARRIES ALL SEVEN OF `US-BIL-026`'s LINE FIELDS, and
 *      the money columns really render RIGHT — read as COMPUTED text-align,
 *      which is the only way DEF-2438 can be seen at all.
 *  11  EVERY PER-SERVICE SUBTOTAL ON SCREEN IS THE SERVER'S OWN 2dp STRING,
 *      compared against `GET /invoices/{id}` fetched in the same run — and the
 *      4dp stored figure is asserted ABSENT, so a second rounding here fails.
 *  12  THE TIE-OUT ON SCREEN IS THE SERVER'S VERDICT, and DEF-2429's misfiled
 *      minimum-bill note appears exactly when the bucket holds one.
 *  13  EVERY TAX AUTHORITY THE SERVER NAMED IS DRAWN (BR-BIL-069), **AND EACH
 *      ONE'S SUBTOTAL IS ON THE SCREEN** — `OQ-1190`, closed by the PO on
 *      2026-08-31: *"(a) Add a per-authority subtotal to the bill and the
 *      finance screens"*. Until that ruling this assertion said the OPPOSITE
 *      (that the page STATED no per-authority total existed), and it is
 *      REPLACED rather than kept beside the new one: a check asserting a figure
 *      and a check asserting the sentence that says there is no figure cannot
 *      both be right, and the pair would pass whichever way the screen went.
 *      Each figure is compared against the server's own `taxes_by_authority`
 *      fetched in the same run, asserted **greater than zero** as well as
 *      correct, with the 4dp stored scale asserted ABSENT; the drawn figures
 *      are added up and must equal the bill's own tax total; the VERDICT is the
 *      server's; and no `tax_id` appears in the panel's visible text (B14 rule
 *      31). A bill with no stamped tax reports `⊘ NOT exercised` rather than
 *      passing quietly.
 *  14  NO RAW CHARGE ID REACHES A CLERK (DEF-2428 / DEF-2432).
 *  16  NO CELL OF THE LINES TABLE AND NO LINE OF THE DOCUMENT TAB IS A RAW
 *      DATABASE ID (DEF-2716 / B14 rule 31), and the run row NAMES its run —
 *      clicked, so a link onto a screen that does not exist cannot pass.
 *
 *      ⚠ **TO EXERCISE THE TWO FALLBACKS YOU HAVE TO BREAK A BILL, and the
 *      product will not let you do it through the product** — `invoice_lines`
 *      carries a `trg_invoice_line_immutable` trigger (hard rule 4) and the
 *      seeded chart resolves every stamp, so on `seed_demo` data both columns
 *      take their FIRST branch and this check reports that it did not exercise
 *      them rather than passing quietly. In a THROWAWAY database:
 *
 *        ALTER TABLE invoice_lines
 *          DROP CONSTRAINT invoice_lines_tariff_version_id_9749d01a_fk_tariff_versions_id;
 *        ALTER TABLE invoice_lines_2026 DISABLE TRIGGER trg_invoice_line_immutable;
 *        UPDATE invoice_lines SET gl_account_id = 'dead0000-0000-4000-8000-000000000001',
 *               tariff_version_id = 'dead0000-0000-4000-8000-000000000002'
 *         WHERE invoice_id = '<the bill you pass as SMOKE_BILL>';
 *        ALTER TABLE invoice_lines_2026 ENABLE TRIGGER trg_invoice_line_immutable;
 *
 *      That is the DEF-937 state — a stamp the chart cannot name — reached
 *      without deleting a chart row four other tables have a foreign key to.
 *  17  **TASK 2 — EVERY REFUSAL ON THIS SCREEN STILL SAYS WHY (BR-SHL-025).**
 *      Task 2's whole content is *"each rendering disabled WITH ITS REASON"*,
 *      and until this was added NOTHING read it in a browser: the only
 *      `disabled` in this file was the bills-list download glyph (task 10). The
 *      check is a PROPERTY rather than a list — **no button anywhere on the bill
 *      is disabled without a non-empty reason** — so a state added next month is
 *      covered without editing this file, and the three the screen has today are
 *      named individually on top of it.
 *
 *      ⚠ **A REASON IS CLERK-FACING COPY, so B14 rule 32 clause 4 reaches it.**
 *      The decision log of 2026-08-31 settled that a tooltip is a screen — *"a
 *      tooltip is clerk-facing, and `BR-MET-121` in a tooltip is still
 *      `BR-MET-121` on the screen"* — so every reason is read for a rule id, a
 *      `snake_case` token and a uuid, exactly as the visible text is.
 *
 *      ⚠ **AND THE DRAFT HALF CANNOT BE EXERCISED ON ANY DATABASE IN THIS
 *      REPO — see `DEF-2901`.** Three of the four refusals task 2 keeps are
 *      DRAFT states (nothing is stamped until issue, a draft is re-run rather
 *      than corrected, a draft is not voided), and `seed_demo` seeds 93 ISSUED
 *      bills and no draft at all. A run over a fresh period breaks on every one
 *      of its 47 accounts for want of a read, and a run over a seeded period is
 *      refused by hard rule 6 — measured, both, on 2026-09-01. The run reports
 *      those assertions NOT EXERCISED rather than passing over them.
 *
 *
 *      **PROVED RED FIRST, TWICE, EACH ON THE DEFECT IT IS WRITTEN FOR (law 7),
 *      with a `vite build` between every sabotage and every run.**
 *      (a) `GuardedButton` was made to drop `title={props.reason}` — BR-SHL-025
 *      failing exactly as it would in production:
 *
 *          ⛔ task 2 / BR-SHL-025: no control on this bill is disabled without a
 *             reason (Print bill · Cancel this bill)
 *          ⛔ task 2: and it says why — ""
 *          ⛔ task 2: "Print bill" is either live or refuses WITH a reason (refused: "")
 *
 *      (b) ` (bill_run_id)` was appended to `billing.bill.action.voidBlocked`,
 *      which is DEF-2881's leak one surface along:
 *
 *          ⛔ task 2 / B14 rule 32 clause 4: no refusal reason carries an
 *             internal code (Cancel this bill: Before a bill is cancelled …)
 *
 *      Restored and rebuilt: all six green. The seven failures this file already
 *      reports on `sbh_cr054w1` are DATA — that seed issues its 93 bills with no
 *      locked copy and the tenant has written no bill copy — and were measured
 *      IDENTICAL by running the branch tip's own copy of this file against the
 *      same database before any of this was added.
 *
 *  15  THE DOCUMENT'S MESSAGE AND WAYS-TO-PAY ARE PROSE — computed
 *      `white-space: pre-line` and a real reading measure — and **NO LATE-FEE
 *      FIGURE IS INVENTED ANYWHERE ON THE PAGE** (CR-052 task 11).
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4231";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const BILL = process.env.SMOKE_BILL ?? "";
const SUPERSEDED = process.env.SMOKE_BILL_SUPERSEDED ?? "";
// A DRAFT bill, for task 2's three draft-only refusals. `seed_demo` has none
// (DEF-2901), so this is usually empty and those assertions report NOT
// exercised rather than passing over a screen they never opened.
const DRAFT_BILL = process.env.SMOKE_BILL_DRAFT ?? "";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr053-bill-surface";
const VIEWPORT = { width: 1440, height: 1000 };

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

/** Something this run could NOT exercise, said out loud.
 *
 *  ⚠ A run that skipped an assertion because the DATA did not reach it has not
 *  passed that assertion, and a silent skip is the shape of a check that cannot
 *  fail — six of which this repo recorded in one day. Printed as `⊘`, so a
 *  reader scanning ticks sees the hole. */
const notes = [];
function note(message) {
  console.log(`   ⊘ ${message}`);
  notes.push(message);
}

const SIDEWAYS = `Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)`;

/** The bill detail's Document tab, as a browser sees it. */
const READ_DOCUMENT_TAB = `(() => {
  const rect = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) };
  };
  const printLink = [...document.querySelectorAll("a")].find(
    (a) => (a.getAttribute("data-bil") || "") === "print-bill",
  );
  const frame = document.querySelector('[data-bil="printable-page"] iframe');
  const headings = [...document.querySelectorAll("h3")].map((h) => ({
    text: h.textContent.trim(),
    y: Math.round(h.getBoundingClientRect().y),
  }));
  const customerLink = [...document.querySelectorAll("a")].find(
    (a) => a.textContent.trim() === "Open the bill as the customer received it",
  );
  // ── DEF-2716 / B14 rule 31 — the run row ────────────────────────────────
  // The run this bill came from is a FACT with an internal key behind it, and
  // the key is what this row printed until 2026-08-31. Read the VISIBLE text
  // and the link, never the source: an id in a data attribute is evidence for
  // support and is exactly what the rule asks for, so a check that greps the
  // markup would fail on the fix.
  const runRow = document.querySelector('[data-bil="bill-run"]');
  const runLink = runRow ? runRow.querySelector("a") : null;
  return {
    printHref: printLink ? printLink.getAttribute("href") : null,
    printIsDisabledButton: [...document.querySelectorAll("button")].some(
      (b) => b.getAttribute("aria-label") === "Print bill" || b.textContent.trim() === "Print bill",
    ),
    frameSrc: frame ? frame.getAttribute("src") : null,
    frameBox: rect(frame),
    headings,
    customerHref: customerLink ? customerLink.getAttribute("href") : null,
    runRowPresent: runRow !== null,
    runRowText: runRow ? (runRow.innerText || "").replace(/\\s+/g, " ").trim() : null,
    runHref: runLink ? runLink.getAttribute("href") : null,
    // Every line of the page a person can actually read, filtered to the ones
    // carrying a uuid. Reading innerText is the point: it is what a clerk sees.
    uuidLinesOnPage: (document.body.innerText || "")
      .split("\\n")
      .map((one) => one.trim())
      .filter((one) =>
        /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i.test(one),
      ),
  };
})()`;

/**
 * The CHARGES tab, measured — CR-053 tasks 6 and 8.
 *
 * ⚠ **`getComputedStyle`, NOT `className` — THIS IS THE WHOLE REASON THE
 * ALIGNMENT LINES ARE HERE.** `DEF-2438`: `PlainTable` puts `[&_td]:text-left`
 * on the TABLE, which compiles to a descendant selector and outranks a plain
 * `text-right` on the cell, so every money column in this kit has rendered
 * LEFT since CR-023 while `toHaveClass("text-right")` passed on every one of
 * them. Only a browser can tell a rendered utility from a class name in the
 * DOM, and reading the computed value is the only assertion that can.
 */
const READ_CHARGES_TAB = `(() => {
  const y = (el) => (el ? Math.round(el.getBoundingClientRect().y) : null);
  const text = (el) => (el ? (el.innerText || "").replace(/\\s+/g, " ").trim() : null);
  const table = document.querySelector('[data-plaintable]');
  const linesTable = [...document.querySelectorAll("table")].find((t) =>
    [...t.querySelectorAll("thead th")].some((th) => th.textContent.trim() === "Accounting code"),
  );
  const headers = linesTable
    ? [...linesTable.querySelectorAll("thead th")].map((th) => th.textContent.trim())
    : [];
  // The AMOUNT cell of the first body row of the lines table, and the same
  // column's header - both must read right.
  const amountIndex = headers.indexOf("Amount");
  const firstAmount =
    linesTable && amountIndex >= 0
      ? [...linesTable.querySelectorAll("tbody tr")]
          .map((tr) => tr.children[amountIndex])
          .find((td) => td && td.tagName === "TD")
      : null;
  const byService = document.querySelector('[data-bil="charges-by-service"]');
  const serviceRows = byService
    ? [...byService.querySelectorAll('[data-bil="service-subtotal"]')].map((tr) => ({
        service: tr.getAttribute("data-service"),
        cells: [...tr.children].map((td) => td.textContent.trim()),
        amountAlign: getComputedStyle(tr.children[2]).textAlign,
      }))
    : [];
  const billLevel = byService
    ? byService.querySelector('[data-bil="bill-level-subtotal"]')
    : null;
  const taxes = document.querySelector('[data-bil="taxes-by-authority"]');
  const authorities = taxes
    ? [...taxes.querySelectorAll('[data-bil="tax-authority"]')].map((el) => el.textContent.trim())
    : [];
  const tieOut = document.querySelector('[data-bil="charges-tie-out"]');
  const due = [...document.querySelectorAll("h3")].find((h) => h.textContent.trim() === "When this is due");
  return {
    headers,
    amountAlign: firstAmount ? getComputedStyle(firstAmount).textAlign : null,
    amountHeadAlign:
      linesTable && amountIndex >= 0
        ? getComputedStyle(linesTable.querySelectorAll("thead th")[amountIndex]).textAlign
        : null,
    serviceRows,
    billLevelText: text(billLevel),
    billLevelAlign: billLevel ? getComputedStyle(billLevel.children[2]).textAlign : null,
    authorities,
    authoritySubtotalNote: text(document.querySelector('[data-bil="no-authority-subtotal"]')),
    // ── OQ-1190 (PO 2026-08-31) — WHAT EACH AUTHORITY IS OWED ─────────────
    // Read as the RENDERED TEXT of the amount cell, keyed on the tax_id the
    // row carries as a data attribute. The id is never the visible value of
    // anything (B14 rule 31); it is here only so the figure can be matched
    // against the server's own bucket rather than against position in a list.
    authoritySubtotals: taxes
      ? [...taxes.querySelectorAll('[data-bil="authority-subtotal"]')].map((tr) => ({
          taxId: tr.getAttribute("data-tax-id"),
          label: tr.children[0].textContent.trim(),
          amount: tr.children[1].textContent.trim(),
          amountAlign: getComputedStyle(tr.children[1]).textAlign,
        }))
      : [],
    taxesTieOut: text(document.querySelector('[data-bil="taxes-tie-out"]')),
    taxesTieOutFlag: document.querySelector('[data-bil="taxes-tie-out"]')
      ? document.querySelector('[data-bil="taxes-tie-out"]').getAttribute("data-ties-out")
      : null,
    // Every visible string inside the tax panel, for the id-leak check below.
    taxPanelText: taxes ? taxes.textContent : "",
    tieOut: text(tieOut),
    tiesOut: tieOut ? tieOut.getAttribute("data-ties-out") : null,
    minimumMisfiled: text(document.querySelector('[data-bil="minimum-misfiled"]')),
    chargeCodeAbsent: text(document.querySelector('[data-bil="line-charge-code-absent"]')),
    lateTerms: text(document.querySelector('[data-bil="late-terms"]')),
    panelOrder: [...document.querySelectorAll("h3")]
      .map((h) => ({ text: h.textContent.trim(), y: y(h) }))
      .filter((h) =>
        ["Amount due", "What each service cost", "Charges on this bill", "Tax on this bill, by authority", "When this is due"].includes(h.text),
      ),
    // ⚠ THE ID LEAK CHECK. A uuid anywhere in the tab's own text is DEF-2432's
    //    shape; the accounting-code column keeps its own documented fallback,
    //    so this looks only at the kind note under a description.
    uuidInKindNotes: [...document.querySelectorAll('[data-bil="line-kind"]')]
      .map((el) => el.parentElement.textContent)
      .filter((t) => /[0-9a-f]{8}-[0-9a-f]{4}-/i.test(t)).length,
    // ⚠ **AND THE SENTENCE THREE LINES UP STOPPED BEING TRUE ON 2026-08-30
    //    (DEF-2716).** *"The accounting-code column keeps its own documented
    //    fallback"* was right when it was written, and B14 rule 31 overtook it:
    //    *"no Databse ID on screen - that is a rule"*. So this reader now covers
    //    EVERY CELL of the lines table, which is the thing the narrow version
    //    could not do — and is how one table on one screen came to state an
    //    absence in one column and print a uuid two columns over.
    //
    //    READ AS RENDERED TEXT, never as markup: rule 31 explicitly allows the
    //    internal value to ride on the element as evidence for support, so a
    //    check over the markup would go RED on a correct fix.
    uuidCells: linesTable
      ? [...linesTable.querySelectorAll("tbody tr")].flatMap((tr) =>
          [...tr.children]
            .map((td, i) => ({
              column: headers[i] ?? "?",
              text: (td.innerText || "").replace(/\\s+/g, " ").trim(),
            }))
            .filter((cell) => /[0-9a-f]{8}-[0-9a-f]{4}-/i.test(cell.text)),
        )
      : [],
    // The two cells this defect is about, by their own hooks — so a PASS can
    // say WHAT each column reads now, not merely that no uuid was found.
    glUnreadable: text(document.querySelector('[data-bil="line-gl-unreadable"]')),
    rateVersionUnreadable: text(
      document.querySelector('[data-bil="line-rate-version-unreadable"]'),
    ),
    tableCount: document.querySelectorAll("table").length,
    plainTablePresent: table !== null,
  };
})()`;

/** The bill DOCUMENT's message/ways-to-pay block — CR-052 task 11. */
const READ_BILL_COPY = `(() => {
  const panel = document.querySelector('[data-bil="bill-copy"]');
  const body = document.body.innerText || "";
  const values = panel
    ? [...panel.querySelectorAll('[data-bil="bill-copy-value"]')].map((el) => ({
        text: el.textContent.trim().slice(0, 120),
        whiteSpace: getComputedStyle(el).whiteSpace,
        width: Math.round(el.getBoundingClientRect().width),
      }))
    : [];
  const absents = panel ? [...panel.querySelectorAll('[data-bil="bill-copy-absent"]')] : [];
  const note = panel ? panel.querySelector('[data-bil="bill-copy-consequence"]') : null;
  const heading = [...document.querySelectorAll("h3")].find((h) => h.textContent.trim() === "Messages");
  return {
    present: panel !== null,
    panelY: panel ? Math.round(panel.getBoundingClientRect().y) : null,
    fieldCount: panel ? panel.querySelectorAll('[data-bil="bill-copy-field"]').length : 0,
    values,
    absentCount: absents.length,
    absentTitles: absents.map((el) => (el.getAttribute("title") || "").slice(0, 60)),
    absentRefs: absents.map((el) => el.getAttribute("data-br-ref")),
    consequence: note ? note.textContent.trim() : null,
    headingY: heading ? Math.round(heading.getBoundingClientRect().y) : null,
    // ⚠ NO INVENTED LATE-FEE COPY, ANYWHERE ON THE PAGE. ⚠ **ASSERTED ONLY ON
    //    A BILL WHOSE TENANT HAS WRITTEN NONE.** When a tenant HAS written its
    //    copy the page prints the tenant's own late-fee sentence, 1.5% and all
    //    — that is the feature — so asserting this on the prose case below
    //    would be a check that fails on correct behaviour.
    inventedLateFee: ["1.5%", "$5.00", "greater of", "late fee of"].filter((needle) =>
      body.includes(needle),
    ),
    // The server's engineering prose must not be the headline (DEF-2715).
    engineeringProseOnScreen: body.includes("Nothing here composes one for them"),
  };
})()`;

/** The Corrections tab's standing line. */
const READ_CHAIN_TAB = `(() => {
  const body = document.body.innerText || "";
  const latest = document.querySelector('[data-bil="chain-latest"]');
  const superseded = document.querySelector('[data-bil="chain-superseded"]');
  return {
    latest: latest ? latest.innerText.trim() : null,
    superseded: superseded ? superseded.innerText.trim() : null,
    supersededHref: superseded ? (superseded.querySelector("a") || {}).getAttribute?.("href") ?? null : null,
    mentionsCurrentBill: body.includes("current bill"),
  };
})()`;

/** The list's toolbar, row actions and pager, measured. */
const READ_LIST = `(() => {
  const toolbar = document.querySelector(".table-toolbar");
  // Only CONTROLS: the toolbar's flex spacer has width and no height, and a
  //    zero-height element sits at a single Y that overlaps nothing, so leaving
  //    it in makes the overlap test below fail on a toolbar that is fine.
  const kids = toolbar
    ? [...toolbar.children].filter((el) => {
        const r = el.getBoundingClientRect();
        return r.width > 0 && r.height > 0;
      })
    : [];
  // WARNING: the first version of this counted distinct top offsets and reported
  //    "4 rows" for a toolbar that was plainly one. A 40px search box beside a
  //    32px button has a different top on the same line, so the count measured
  //    control HEIGHT and reported it as WRAPPING - a check whose output cannot
  //    distinguish pass from fail, which DEF-182 says is worse than no check.
  //    The question is whether the controls share a line, and the answer is
  //    whether their vertical ranges all OVERLAP.
  //    (No backticks in here: this block lives inside a template literal, and a
  //    backtick around a word closes the string - which is how this comment
  //    broke the harness once already.)
  const spans = kids.map((el) => {
    const r = el.getBoundingClientRect();
    return { top: Math.round(r.top), bottom: Math.round(r.bottom) };
  });
  const oneRow = spans.length > 0
    && Math.max(...spans.map((s) => s.top)) < Math.min(...spans.map((s) => s.bottom));
  const download = document.querySelector('[data-download="button"]');
  const firstRow = document.querySelector("tbody tr");
  const actionCell = firstRow ? firstRow.lastElementChild : null;
  const actions = actionCell
    ? [...actionCell.querySelectorAll("a,button")].map((el) => ({
        name: el.getAttribute("aria-label"),
        title: el.getAttribute("title"),
        tag: el.tagName.toLowerCase(),
        w: Math.round(el.getBoundingClientRect().width),
        h: Math.round(el.getBoundingClientRect().height),
        svg: el.querySelector("svg") !== null,
      }))
    : [];
  const pager = document.querySelector(".table-pager");
  const size = pager ? pager.querySelector("select") : null;
  return {
    toolbarOneRow: oneRow,
    toolbarSpans: spans,
    toolbarChildren: kids.length,
    searchPlaceholder: (document.querySelector('.table-toolbar input[type="search"]') || {}).placeholder ?? null,
    hasFilterControl: !!document.querySelector(".table-toolbar details summary"),
    downloadPresent: !!download,
    downloadDisabled: download ? download.disabled : null,
    downloadReason: download && download.closest("span[title]") ? download.closest("span[title]").getAttribute("title") : null,
    actions,
    pagerPresent: !!pager,
    pagerText: pager ? pager.innerText.replace(/\\s+/g, " ").trim() : null,
    pageSize: size ? size.value : null,
    pagerBelowTable: pager && document.querySelector("table")
      ? Math.round(pager.getBoundingClientRect().top) >= Math.round(document.querySelector("table").getBoundingClientRect().bottom)
      : null,
  };
})()`;

(async () => {
  if (BILL === "") {
    console.log("⛔ give SMOKE_BILL an ISSUED invoice id");
    process.exit(2);
  }

  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });

  console.log(`cr053: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);

  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });
  console.log("   signed in");

  // ── TASKS 1, 3 and 4 — the bill's Document tab ──────────────────────────
  console.log(`\n── the bill's Document tab (${BILL.slice(0, 8)}) ──`);
  await page.goto(`${BASE}/${TENANT}/billing/bills/${BILL}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2500);
  await page.screenshot({ path: join(OUT, "document-tab.png"), fullPage: true });
  const doc = await page.evaluate(READ_DOCUMENT_TAB);

  check(doc.printHref !== null, `task 1: Print bill is a LIVE link (href=${doc.printHref})`);
  check(!doc.printIsDisabledButton, "task 1: it is no longer a switched-off button");
  if (doc.printHref !== null) {
    const answer = await page.request.get(`${BASE}${doc.printHref}`);
    const type = answer.headers()["content-type"] ?? "";
    const bytes = (await answer.body()).length;
    check(
      answer.status() === 200 && type.startsWith("application/pdf"),
      `task 1: the URL it names really answers a PDF (${answer.status()} ${type}, ${bytes} bytes)`,
    );
  }
  check(doc.frameSrc === doc.printHref, "task 3: the embedded page is the SAME url the control opens");
  check(
    doc.frameBox !== null && doc.frameBox.w > 600 && doc.frameBox.h > 400,
    `task 3: the printable page has a real box on screen (${JSON.stringify(doc.frameBox)})`,
  );

  const RULED = ["Customer's bill", "Where this bill came from", "How this bill was produced", "Record check", "Delivery"];
  const found = RULED.map((label) => doc.headings.find((h) => h.text === label));
  check(found.every(Boolean), `task 4: all five panels are on screen (${found.filter(Boolean).length}/5)`);
  if (found.every(Boolean)) {
    const ys = found.map((h) => h.y);
    check(
      ys.every((y, i) => i === 0 || y >= ys[i - 1]),
      `task 4: they are in the ruled order, measured top to bottom (${ys.join(" < ")})`,
    );
    check(
      doc.frameBox !== null && doc.frameBox.y < ys[0],
      "task 3: the document is ABOVE the panels that describe it",
    );
  }

  // ── TASK 2 — THE REFUSALS THAT ARE STILL TRUE, READ OFF THE SCREEN ──────
  // Task 2 is *"keep the three refusals that are still true, each rendering
  // disabled WITH its reason"*, and it has two halves that fail in opposite
  // directions: a refusal that has stopped being true is DEF-2451 (a control
  // apologising for an endpoint that shipped), and a refusal that loses its
  // reason is BR-SHL-025 (a dead button nobody can explain). Both are only
  // visible in rendered output.
  const REFUSALS = `(() => {
    const buttons = [...document.querySelectorAll("button")].map((b) => ({
      label: (b.innerText || "").trim(),
      disabled: b.disabled === true || b.getAttribute("aria-disabled") === "true",
      reason: b.getAttribute("title") || "",
    }));
    const links = [...document.querySelectorAll("a")].map((a) => ({
      label: (a.innerText || "").trim(),
      href: a.getAttribute("href") || "",
    }));
    return { buttons, links };
  })()`;
  const refusals = await page.evaluate(REFUSALS);
  const silent = refusals.buttons.filter((b) => b.disabled && b.reason.trim() === "");
  check(
    silent.length === 0,
    `task 2 / BR-SHL-025: no control on this bill is disabled without a reason (${
      silent.map((b) => b.label).join(" · ") || "none silent"
    })`,
  );
  // Rule 32 clause 4 — a tooltip is a screen (decision log 2026-08-31).
  const codedReasons = refusals.buttons
    .filter((b) => b.disabled)
    .filter((b) =>
      /\b[a-z]+_[a-z_]+\b/.test(b.reason) ||
      /\b(?:BR|US|EP|OQ|DEF|GT|IS|ADR)-[A-Z]{0,3}-?\d{3,5}\b/.test(b.reason) ||
      /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i.test(b.reason),
    );
  check(
    codedReasons.length === 0,
    `task 2 / B14 rule 32 clause 4: no refusal reason carries an internal code (${
      codedReasons.map((b) => `${b.label}: ${b.reason.slice(0, 60)}`).join(" · ") || "none"
    })`,
  );
  // VOID is the one refusal on an ISSUED bill that is still true — US-BIL-027's
  // flow does not exist — and it holds the header's single primary slot
  // (BR-SHL-044), in the danger tier because it is the only control here that
  // changes the bill at all.
  // ⚠ ITS LABEL IS "Cancel this bill", NOT "Void". `billing.bill.action.void` is
  // the KEY; the words a clerk reads are the catalogue's, and a check that
  // matched the key's name would silently find nothing and report a skip — which
  // is what the first run of this block did.
  const voidButton = refusals.buttons.find((b) => /cancel this bill/i.test(b.label));
  if (voidButton === undefined) {
    note("NOT exercised: no Void control was on the page, so task 2's live refusal was not read");
  } else {
    check(voidButton.disabled, "task 2: Void is still refused on an issued bill (its flow is unbuilt)");
    check(
      voidButton.reason.trim().length > 0,
      `task 2: and it says why — "${voidButton.reason.slice(0, 80)}"`,
    );
  }
  // THE OTHER HALF: each of these two must be EITHER a live control OR a
  // refusal that says something.
  //
  // ⚠ **AND IT DELIBERATELY DOES NOT ASSERT "NO REFUSAL CLAIMS THE PRODUCT
  // CANNOT DO IT", WHICH IS WHAT A FIRST DRAFT OF THIS BLOCK DID.** DEF-2451
  // was a refusal saying *"the endpoint that renders it has not been built"*
  // about an endpoint that HAD been built, so the tempting check is to ban that
  // sentence. It cannot work, and the screen it is pointed at is the proof:
  // `billing.bill.action.voidBlocked` says the same thing — *"the endpoint that
  // does it has not been built"* — and it is TRUE, because US-BIL-027's flow
  // genuinely does not exist. A browser can read the claim and cannot check it.
  // A ban would have failed on the honest sentence and passed on the stale one
  // the day the endpoint landed, which is worse than not checking at all.
  // Measured on 2026-09-01, both sentences on one screen.
  //
  // ⚠ It is also deliberately not "Print must be a live link". Whether a bill
  // has a locked copy is DATA (`seed_demo` issues bills without one), and an
  // assertion that a screen must be in the state this database happens to
  // produce is the kind that gets deleted the first time someone reseeds. Task
  // 1's own assertions above already cover the live case where the data reaches
  // it.
  for (const [name, pattern] of [["Print bill", /print/i], ["Fix this bill", /^fix this bill$/i]]) {
    const asButton = refusals.buttons.find((b) => pattern.test(b.label));
    const asLink = refusals.links.find((a) => pattern.test(a.label));
    const live = asLink !== undefined || (asButton !== undefined && !asButton.disabled);
    const reason = asButton && asButton.disabled ? asButton.reason : "";
    check(
      live || reason.trim().length > 0,
      `task 2: "${name}" is either live or refuses WITH a reason (${live ? "live" : `refused: "${reason.slice(0, 60)}"`})`,
    );
  }
  // ⚠ THE DRAFT REFUSALS — DEF-2901. Three of task 2's four states only exist
  // on a DRAFT bill and no database in this repo has one.
  if (DRAFT_BILL === "") {
    note(
      "NOT exercised: SMOKE_BILL_DRAFT was not set — the three DRAFT refusals (nothing stamped until issue, a draft is re-run not corrected, a draft is not voided) were not read on any screen; see DEF-2901 for why seed_demo cannot produce one",
    );
  } else {
    await page.goto(`${BASE}/${TENANT}/billing/bills/${DRAFT_BILL}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(2000);
    await page.screenshot({ path: join(OUT, "draft-refusals.png"), fullPage: true });
    const draft = await page.evaluate(REFUSALS);
    const draftSilent = draft.buttons.filter((b) => b.disabled && b.reason.trim() === "");
    check(draftSilent.length === 0, `task 2: on a DRAFT bill too, no refusal is silent (${draftSilent.length})`);
    const reasons = draft.buttons.filter((b) => b.disabled).map((b) => b.reason);
    check(
      new Set(reasons).size === reasons.length,
      "task 2: each refusal says the reason true of THAT control, not one sentence three times",
    );
    await page.goto(`${BASE}/${TENANT}/billing/bills/${BILL}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(1500);
  }

  // ── DEF-2716 / B14 rule 31 — the run is NAMED, not keyed ────────────────
  // This row printed `bill_run_id` because EP-BIL-01's run screens did not
  // exist when it was written, and *"a link onto a placeholder is 'built is not
  // wired' wearing a different hat"* was the right call at the time. CR-051
  // built them. So the row becomes the link it always wanted to be, and the
  // clerk reads a control instead of a uuid.
  check(
    doc.runRowPresent,
    `DEF-2716: the Where-this-came-from panel has a run row (${doc.runRowText})`,
  );
  check(
    doc.uuidLinesOnPage.length === 0,
    `DEF-2716 / B14 rule 31: no uuid is visible anywhere on the Document tab ` +
      `(${doc.uuidLinesOnPage.length} leaked${
        doc.uuidLinesOnPage.length > 0 ? `: ${doc.uuidLinesOnPage.join(" · ")}` : ""
      })`,
  );
  if (doc.runHref !== null && doc.runHref !== undefined) {
    // …and it is CLICKED. DEF-2450 on the panel above is the standing reason:
    // a plausible href is exactly what a dead link looks like from source.
    await page.click('[data-bil="bill-run"] a');
    await page.waitForTimeout(2500);
    const landedRun = await page.evaluate(
      `({ url: location.pathname + location.search, text: (document.body.innerText || "").slice(0, 400) })`,
    );
    await page.screenshot({ path: join(OUT, "bill-run-landed.png"), fullPage: true });
    check(
      !/not found|404/i.test(landedRun.text) && landedRun.url.includes("/billing/run"),
      `DEF-2716: clicking it arrives at the run it came from (${landedRun.url})`,
    );
    await page.goto(`${BASE}/${TENANT}/billing/bills/${BILL}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(2000);
  } else {
    check(false, "DEF-2716: the run row is a link to the run that made this bill");
  }

  check(
    doc.customerHref === `/${TENANT}/billing/bills/${BILL}/document`,
    `task 4 / DEF-2450: the customer's-bill link is an in-app route (${doc.customerHref})`,
  );
  // …and it is CLICKED, because a plausible href is what the defect looked like.
  if (doc.customerHref) {
    await page.click('a:has-text("Open the bill as the customer received it")');
    await page.waitForTimeout(2000);
    const landed = await page.evaluate(
      `({ url: location.pathname, text: (document.body.innerText || "").slice(0, 200) })`,
    );
    await page.screenshot({ path: join(OUT, "customer-bill-landed.png"), fullPage: true });
    check(
      landed.url.endsWith("/document") && !/not found|404/i.test(landed.text),
      `task 4 / DEF-2450: clicking it arrives at the bill document (${landed.url})`,
    );
  }

  let sideways = await page.evaluate(SIDEWAYS);
  check(sideways === 0, `the bill page does not scroll sideways (${sideways}px)`);

  // ── TASK 5 — the Corrections tab ────────────────────────────────────────
  console.log("\n── the Corrections tab ──");
  await page.goto(`${BASE}/${TENANT}/billing/bills/${BILL}?tab=chain`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: join(OUT, "chain-current.png"), fullPage: true });
  const current = await page.evaluate(READ_CHAIN_TAB);
  check(
    current.latest !== null,
    `task 5: an uncorrected bill says it is the current one ("${current.latest}")`,
  );

  if (SUPERSEDED !== "") {
    await page.goto(`${BASE}/${TENANT}/billing/bills/${SUPERSEDED}?tab=chain`, {
      waitUntil: "networkidle",
    });
    await page.waitForTimeout(1500);
    await page.screenshot({ path: join(OUT, "chain-superseded.png"), fullPage: true });
    const old = await page.evaluate(READ_CHAIN_TAB);
    check(
      old.superseded !== null,
      `task 5: a SUPERSEDED bill says so, and names its replacement ("${old.superseded}")`,
    );
    check(
      old.supersededHref !== null && old.supersededHref.includes("/billing/bills/"),
      `task 5: the replacement is a link a clerk can follow (${old.supersededHref})`,
    );
    check(
      current.latest !== old.latest,
      "task 5: the two states are VISIBLY different — asserted as a comparison",
    );
  }

  // ── CR-053 TASKS 6 and 8 — the Charges tab, every scenario on one screen ─
  console.log("\n── the bill's Charges tab (CR-053 tasks 6 + 8) ──");
  await page.goto(`${BASE}/${TENANT}/billing/bills/${BILL}?tab=lines`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: join(OUT, "charges-tab.png"), fullPage: true });

  // WHAT THE SERVER ACTUALLY SAID, fetched here so every figure below is
  // compared against the answer rather than against a number typed in a check.
  const detail = await (await page.request.get(`${BASE}/api/${TENANT}/invoices/${BILL}`)).json();
  const cbs = detail.charges_by_service ?? null;
  const charges = await page.evaluate(READ_CHARGES_TAB);

  const SEVEN = ["Description", "Usage", "Rate", "Amount", "Taxable", "Accounting code", "Rate version"];
  check(
    SEVEN.every((h) => charges.headers.includes(h)),
    `task 8 / US-BIL-026: all seven line fields are column headers (${charges.headers.join(" · ")})`,
  );

  // ── DEF-2438, and it is the assertion no test in this repo can make ──────
  check(
    charges.amountAlign === "right",
    `DEF-2438: the Amount column really renders RIGHT — computed text-align=${charges.amountAlign}`,
  );
  check(
    charges.amountHeadAlign === "right",
    `DEF-2438: and so does its header (computed ${charges.amountHeadAlign})`,
  );

  check(cbs !== null, "task 6: the server answers charges_by_service on this bill");
  if (cbs !== null) {
    check(
      charges.serviceRows.length === cbs.services.length,
      `task 6: one row per service the server named (${charges.serviceRows.length} of ${cbs.services.length})`,
    );
    for (const row of cbs.services) {
      const drawn = charges.serviceRows.find((r) => r.service === row.service);
      check(
        drawn !== undefined && drawn.cells.some((c) => c.includes(row.subtotal_display)),
        `task 6: ${row.service} shows the SERVER's own 2dp subtotal ${row.subtotal_display} ` +
          `(drawn: ${drawn ? drawn.cells.join(" | ") : "MISSING"})`,
      );
      check(
        drawn !== undefined && !drawn.cells.some((c) => c.includes(row.subtotal)),
        `task 6 / rule 2: the 4dp stored figure ${row.subtotal} is NOT on the screen`,
      );
      check(
        drawn !== undefined && drawn.amountAlign === "right",
        `DEF-2438: the per-service amount renders right (${drawn ? drawn.amountAlign : "n/a"})`,
      );
    }
    check(
      charges.billLevelText !== null && charges.billLevelText.includes(cbs.bill_level.subtotal_display),
      `task 6: the bill-level bucket states its own figure ${cbs.bill_level.subtotal_display} ("${charges.billLevelText}")`,
    );
    check(
      String(cbs.tie_out.ties_out) === charges.tiesOut,
      `task 6 / BR-BIL-032: the tie-out on screen is the SERVER's verdict (${charges.tiesOut}) — "${charges.tieOut}"`,
    );
    // DEF-2429 — the note appears exactly when the bucket holds the misfiled kind.
    const expectMisfiled = cbs.bill_level.kinds.includes("minimum_adjustment");
    check(
      expectMisfiled === (charges.minimumMisfiled !== null),
      `DEF-2429: the misfiled-minimum note is drawn iff the bucket holds one ` +
        `(kinds=[${cbs.bill_level.kinds.join(",")}], note=${charges.minimumMisfiled === null ? "absent" : "present"})`,
    );
  }

  // ── BR-BIL-069 — whose tax, read from the LINES the server sent ──────────
  const taxLines = (detail.lines ?? []).filter((l) => l.kind === "tax");
  const served = [...new Set(taxLines.map((l) => l.tax_authority).filter(Boolean))];
  check(
    served.every((name) => charges.authorities.includes(name)),
    `task 6 / BR-BIL-069: every authority the server named is on the screen ` +
      `(served: ${served.join(" · ") || "none"}; drawn: ${charges.authorities.join(" · ") || "none"})`,
  );
  // ── OQ-1190 · CLOSED 2026-08-31 — EACH AUTHORITY'S SUBTOTAL IS ON SCREEN ──
  //
  // PO verbatim: *"(a) Add a per-authority subtotal to the bill and the finance
  // screens"*. Until that ruling this check asserted the OPPOSITE — that the
  // page STATED no per-authority total existed — because none did. The
  // absence-note assertion is replaced rather than kept beside the new one: two
  // checks, one asserting a figure and one asserting the sentence saying there
  // is no figure, cannot both be right, and the pair would pass whichever way
  // the screen went.
  //
  // ⚠ **THE FIGURES ARE COMPARED AGAINST THE SERVER'S OWN `taxes_by_authority`
  // FETCHED IN THE SAME RUN**, and the 4dp stored scale is asserted ABSENT — so
  // a screen that rounded a second time fails here even though it would look
  // right. This is the one check that can see it.
  const tba = detail.taxes_by_authority ?? null;
  check(
    tba !== null,
    `OQ-1190: GET /invoices/{id} serves taxes_by_authority (${tba === null ? "MISSING" : `${tba.authorities.length} authorit(ies)`})`,
  );
  if (tba !== null) {
    // NON-VACUOUS. A bill with no tax would make every assertion below trivially
    // true, so the run SAYS it did not exercise them rather than reporting a
    // pass it did not earn.
    if (tba.authorities.length === 0) {
      note(
        `OQ-1190: this bill charges no stamped tax, so the per-authority subtotal ` +
          `assertions were NOT exercised — point SMOKE_BILL at a taxed bill`,
      );
    }
    for (const bucket of tba.authorities) {
      const drawn = charges.authoritySubtotals.find((row) => row.taxId === bucket.tax_id);
      check(
        drawn !== undefined,
        `OQ-1190: ${bucket.authority ?? "an unnamed authority"} has a subtotal row on screen`,
      );
      if (drawn === undefined) continue;
      check(
        drawn.amount.includes(bucket.subtotal_display),
        `OQ-1190: the subtotal on screen is the SERVER's 2dp figure ` +
          `${bucket.subtotal_display} for ${bucket.authority} ("${drawn.amount}")`,
      );
      // A CHECK THAT CAN FAIL BOTH WAYS: the figure must also be REAL money.
      // A block answering 0.00 for every authority would satisfy every
      // string comparison above and tell a clerk filing a return that nobody
      // is owed anything.
      check(
        Number(bucket.subtotal_display) > 0,
        `OQ-1190: ${bucket.authority}'s subtotal is greater than zero ` +
          `(${bucket.subtotal_display}) — 0.00 on a screen a return is filed from ` +
          `reads as "this authority is owed nothing"`,
      );
      check(
        !drawn.amount.includes(bucket.subtotal),
        `OQ-1190 / rule 2: the 4dp stored figure ${bucket.subtotal} is NOT on screen ` +
          `(a second rounding here would be a second money path)`,
      );
      check(
        drawn.amountAlign === "right",
        `DEF-2438: the authority subtotal renders right (${drawn.amountAlign})`,
      );
    }
    // THE FOOTING — this is the whole question. Σ of the authority figures the
    // screen drew must be the bill's own tax total, and the VERDICT must be the
    // server's rather than one this check computes for it.
    const drawnSum = charges.authoritySubtotals.reduce(
      (total, row) => total + Number(row.amount.replace(/[^0-9.-]/g, "")),
      0,
    );
    check(
      Math.abs(drawnSum - Number(tba.tie_out.tax_total_display)) < 0.005,
      `OQ-1190: the authority subtotals ON SCREEN add to the bill's own tax total ` +
        `(${drawnSum.toFixed(2)} vs ${tba.tie_out.tax_total_display})`,
    );
    check(
      String(tba.tie_out.ties_out) === charges.taxesTieOutFlag,
      `OQ-1190 / R1–R7: the tax tie-out on screen is the SERVER's verdict ` +
        `(${charges.taxesTieOutFlag}) — "${charges.taxesTieOut}"`,
    );
    // The pre-ruling sentence must be GONE when the block is served. Leaving it
    // beside real figures would tell a clerk the numbers in front of them do
    // not exist.
    check(
      charges.authoritySubtotalNote === null,
      `OQ-1190: the "no per-authority total is available yet" sentence is gone ` +
        `now that the figures are served ("${charges.authoritySubtotalNote}")`,
    );
    // B14 rule 31 — no tax_id anywhere in the panel's visible text.
    const leakedIds = tba.authorities.filter((bucket) =>
      charges.taxPanelText.includes(bucket.tax_id),
    );
    check(
      leakedIds.length === 0,
      `B14 rule 31: no tax_id is visible in the tax panel (${leakedIds.length} leaked)`,
    );
  }

  // ── DEF-2428 / DEF-2432 — a charge id is never printed at a clerk ────────
  const feeLines = (detail.lines ?? []).filter((l) => l.charge_id !== null);
  check(
    charges.uuidInKindNotes === 0,
    `DEF-2428 / DEF-2432: no raw uuid under any line description ` +
      `(${feeLines.length} line(s) carry a charge_id, ${charges.uuidInKindNotes} leaked)`,
  );

  // ── DEF-2716 / B14 rule 31 — NO CELL OF THIS TABLE IS AN ID ──────────────
  // The rule, ratified 2026-08-30: *"no Databse ID on screen - that is a
  // rule"*. It arrived after the Accounting code and Rate version columns were
  // written, and each of them had a reason to print the id (DEF-937: a blank in
  // a column headed ACCOUNTING CODE reads as *"this line did not post"*). A
  // stated absence keeps that reason and drops the id, which is the choice the
  // charge-code note two columns over had already made.
  //
  // ⚠ **THIS IS THE ONLY CHECK THAT CAN SEE IT.** Rule 31 is a claim about
  // RENDERED output; `G28` inspects catalogue strings and cannot look at a
  // uuid-shaped VALUE, its own status column says so, and 188 green jsdom cases
  // asserted these columns by header without ever reading what was in them.
  check(
    charges.uuidCells.length === 0,
    `DEF-2716 / B14 rule 31: no cell of the lines table is a raw id ` +
      `(${charges.uuidCells.length} leaked${
        charges.uuidCells.length > 0
          ? `: ${[...new Set(charges.uuidCells.map((c) => c.column))].join(" · ")}`
          : ""
      })`,
  );
  // A bill whose stamps still resolve proves nothing about the fallback, so say
  // which case this run actually exercised rather than reporting a quiet pass.
  const unreadableGl = (detail.lines ?? []).filter(
    (l) => l.gl_account_id !== null && l.gl_account_code === null,
  );
  const unreadableVersion = (detail.lines ?? []).filter(
    (l) => l.tariff_version_id !== null && l.tariff_version_label === null,
  );
  if (unreadableGl.length > 0) {
    check(
      charges.glUnreadable !== null,
      `DEF-2716: ${unreadableGl.length} line(s) carry a GL stamp the chart cannot name, and the ` +
        `column says so in words ("${charges.glUnreadable}")`,
    );
  } else {
    console.log(
      "   · every GL stamp on this bill resolves — the DEF-937 fallback was NOT exercised",
    );
  }
  if (unreadableVersion.length > 0) {
    check(
      charges.rateVersionUnreadable !== null,
      `DEF-2716: ${unreadableVersion.length} line(s) carry a rate version rating cannot name, and ` +
        `the column says so in words ("${charges.rateVersionUnreadable}")`,
    );
  } else {
    console.log(
      "   · every rate version on this bill resolves — that fallback was NOT exercised",
    );
  }

  check(
    charges.lateTerms !== null && /own words/.test(charges.lateTerms),
    `task 6: the late-payment panel says whose words the terms are ("${charges.lateTerms}")`,
  );

  const order = charges.panelOrder.map((p) => p.text);
  check(
    order.length >= 4 &&
      charges.panelOrder.every((p, i) => i === 0 || p.y >= charges.panelOrder[i - 1].y),
    `task 6: the panels read top to bottom in one order (${charges.panelOrder.map((p) => `${p.text}@${p.y}`).join(" → ")})`,
  );

  sideways = await page.evaluate(SIDEWAYS);
  check(sideways === 0, `the Charges tab does not scroll sideways (${sideways}px)`);

  // ── CR-052 TASK 11 — the message and ways to pay, on the bill document ───
  console.log("\n── the bill document's message + ways to pay (CR-052 task 11) ──");
  await page.goto(`${BASE}/${TENANT}/billing/bills/${BILL}/document`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2500);
  await page.screenshot({ path: join(OUT, "bill-copy.png"), fullPage: true });
  const copy = await page.evaluate(READ_BILL_COPY);

  check(copy.present, "task 11: the message / ways-to-pay block is on the document");
  check(copy.fieldCount === 2, `task 11: both fields are drawn (${copy.fieldCount})`);
  for (const value of copy.values) {
    check(
      value.whiteSpace === "pre-line",
      `task 11: a tenant's line breaks survive — computed white-space=${value.whiteSpace}`,
    );
    check(
      value.width > 200,
      `task 11: prose gets a reading measure, not a 220px grid cell (${value.width}px)`,
    );
  }
  if (copy.absentCount > 0) {
    check(
      copy.consequence !== null && /late-payment terms/.test(copy.consequence),
      `task 11: an unwritten message says the bill carries no late-payment terms ("${copy.consequence}")`,
    );
    check(
      copy.absentRefs.every((r) => r === "BR-BIL-021"),
      `task 11: the rule stays on the element for support (${copy.absentRefs.join(", ")})`,
    );
    check(
      !copy.engineeringProseOnScreen,
      "task 11 / DEF-2715: the server's engineering sentence is NOT the headline a clerk reads",
    );
  }
  check(
    copy.inventedLateFee.length === 0,
    `task 11: the platform composes NO late-fee copy — nothing invented on the page ` +
      `(${copy.inventedLateFee.join(", ") || "clean"})`,
  );

  sideways = await page.evaluate(SIDEWAYS);
  check(sideways === 0, `the bill document does not scroll sideways (${sideways}px)`);

  // ── TASK 11's OTHER HALF — a tenant that HAS written its copy ────────────
  //
  // ⚠ **WHY THIS ONE CASE IS SERVED A PATCHED BODY, AND WHY THAT IS STILL
  // EVIDENCE.** Every bill in the seeded utility was issued before its tenant
  // wrote a bill message, and `BR-BIL-030` freezes the copy AT ISSUE — so no
  // existing bill can ever show the prose branch, and hard rule 4 forbids
  // editing one to make it. Issuing a fresh bill under the new template needs a
  // cycle run this lane does not own.
  //
  // So the page is handed the SERVER'S OWN RESPONSE for this bill with the two
  // footer values replaced by the copy the tenant really typed — read back
  // from `GET /bill-templates`, not invented here — which is byte for byte
  // what `issue._stamp_bill_copy` will stamp onto the next bill issued under
  // version 2. Everything measured below is the REAL component in a REAL
  // browser; only the body it renders is pinned.
  const library = await (await page.request.get(`${BASE}/api/${TENANT}/bill-templates`)).json();
  const options = (library.current ?? {}).options ?? {};
  const tenantMessage = options.bill_message ?? null;
  const tenantWays = options.ways_to_pay ?? null;

  if (tenantMessage !== null && tenantWays !== null) {
    console.log("\n── …and when the tenant HAS written its copy ──");
    const served = await (
      await page.request.get(`${BASE}/api/${TENANT}/invoices/${BILL}/document`)
    ).json();
    const patched = {
      ...served,
      footer: [
        { label: "Message", value: tenantMessage, absent: null },
        { label: "Ways to pay", value: tenantWays, absent: null },
      ],
    };
    await page.route(`**/api/${TENANT}/invoices/${BILL}/document`, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(patched),
      }),
    );
    await page.goto(`${BASE}/${TENANT}/billing/bills/${BILL}/document`, {
      waitUntil: "networkidle",
    });
    await page.waitForTimeout(2500);
    await page.screenshot({ path: join(OUT, "bill-copy-written.png"), fullPage: true });
    const written = await page.evaluate(READ_BILL_COPY);
    await page.unroute(`**/api/${TENANT}/invoices/${BILL}/document`);

    check(written.fieldCount === 2, `task 11: both fields drawn (${written.fieldCount})`);
    check(
      written.absentCount === 0 && written.consequence === null,
      "task 11: a tenant that HAS written its copy is told nothing about what is missing",
    );
    check(
      written.values.length === 2 && written.values.every((v) => v.whiteSpace === "pre-line"),
      `task 11: the line breaks the tenant typed SURVIVE — computed white-space=` +
        `${written.values.map((v) => v.whiteSpace).join(", ")}`,
    );
    check(
      written.values.every((v) => v.width >= 400),
      `task 11: prose gets a reading measure, not a 220px grid cell ` +
        `(${written.values.map((v) => `${v.width}px`).join(", ")})`,
    );
    check(
      written.values.some((v) => v.text.includes("1.5% per month")),
      `task 11: the TENANT's own late-fee sentence prints, word for word ` +
        `("${(written.values[0] ?? {}).text ?? ""}")`,
    );
  } else {
    check(
      false,
      "task 11: this tenant has written no bill copy, so the prose half was not exercised — " +
        "write one through POST /bill-templates/layout and re-run",
    );
  }

  // ── TASKS 10, 11 and 12 — the bills list ────────────────────────────────
  console.log("\n── the All-bills list ──");
  await page.goto(`${BASE}/${TENANT}/billing`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: join(OUT, "bills-list.png"), fullPage: true });
  const list = await page.evaluate(READ_LIST);

  check(
    list.toolbarOneRow,
    `task 10 / B14 rule 12: the toolbar is ONE row — ${list.toolbarChildren} controls sharing a line ` +
      `(${list.toolbarSpans.map((s) => `${s.top}-${s.bottom}`).join(" ")})`,
  );
  check(list.searchPlaceholder !== null, `task 10: one search box ("${list.searchPlaceholder}")`);
  check(list.hasFilterControl, "task 10: one filter set");
  check(list.downloadPresent, "task 10: one download glyph");
  check(
    list.downloadDisabled === true && (list.downloadReason ?? "").length > 0,
    `task 10 / BR-SHL-025: it is disabled WITH its reason ("${list.downloadReason}")`,
  );

  check(
    list.actions.length > 0 && list.actions.length <= 2,
    `task 11 / B14 rule 15: at most two visible row actions (${list.actions.length})`,
  );
  check(
    list.actions.every((a) => a.svg && (a.name ?? "").length > 0),
    `task 11: each is an ICON with an accessible name (${list.actions.map((a) => a.name).join(", ")})`,
  );
  check(
    list.actions.every((a) => (a.title ?? "").length > 0),
    "task 11: each carries a tooltip",
  );
  check(
    list.actions.every((a) => a.w >= 24 && a.h >= 24),
    `task 11: each is a real clickable box (${list.actions.map((a) => `${a.w}x${a.h}`).join(" ")})`,
  );

  check(list.pagerPresent, `task 12 / B14 rule 16: the pagination footer is on the table`);
  check(list.pagerBelowTable === true, "task 12: it is BELOW the table, not above it");
  console.log(`   pager reads: "${list.pagerText}"`);

  // The remembered size, proved the only way it can be: change it, RELOAD, look.
  await page.selectOption(".table-pager select", "200");
  await page.waitForTimeout(1200);
  await page.goto(`${BASE}/${TENANT}/billing`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2500);
  const after = await page.evaluate(READ_LIST);
  await page.screenshot({ path: join(OUT, "bills-list-remembered.png"), fullPage: true });
  check(
    after.pageSize === "200",
    `task 12 / DEF-2452: the page size SURVIVES A RELOAD (was ${list.pageSize}, now ${after.pageSize})`,
  );

  sideways = await page.evaluate(SIDEWAYS);
  check(sideways === 0, `the bills list does not scroll sideways (${sideways}px)`);

  await browser.close();
  console.log(`\nscreenshots in ${OUT}`);
  if (notes.length > 0) {
    // NOT a failure, and NOT silent either: an assertion the data did not reach
    // has not passed, and a reader counting ticks must be able to see the hole.
    console.log(`\n⊘ ${notes.length} assertion group(s) NOT exercised by this data:`);
    for (const n of notes) console.log(`   · ${n}`);
  }
  if (failures.length > 0) {
    console.log(`\n⛔ ${failures.length} failure(s):`);
    for (const f of failures) console.log(`   · ${f}`);
    process.exit(1);
  }
  console.log("\n✓ every assertion held in a real browser");
})();
