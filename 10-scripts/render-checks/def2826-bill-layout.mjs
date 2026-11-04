#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Defects: DEF-2826 (the page named a layout and drew another) ·
//          DEF-2715 (the page printed the server's engineering prose)
// Screens: S30 → "View the bill as sent"
// Rules:   BR-BIL-026 (a reprint renders the PINNED version, forever) ·
//          B14 rule 31 (nothing internal is the visible value of a field) ·
//          B14 rule 32 clause 4 · hard-won law 6 (no gate reads rendered
//          output) · law 7 (RED first)
// ───────────────────────────────────────────────────────
/**
 * THE BILL DOCUMENT, IN A REAL BROWSER, ON THE PRODUCTION BUNDLE — AND WITH NO
 * DATABASE.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * WHY THIS EXISTS BESIDE `cr052-per-account-template.mjs` RATHER THAN INSTEAD
 * ══════════════════════════════════════════════════════════════════════════
 * That file is the END-TO-END check and it is the better evidence: it drives
 * two REAL bills, issued through real doors, pinned to two real layouts, and it
 * fetches each bill's KEPT COPY as the control. Nothing here replaces it and
 * nothing here should be read as covering what it covers.
 *
 * **It also could not be run in this environment, and that is the whole reason
 * for this file.** It needs a database holding two ISSUED bills, and reaching
 * one is a provisioning project rather than a check: `manage.py seed_demo`
 * deliberately seeds no customers, accounts or bills ("their lanes have not
 * landed — nothing here fakes them"), and `cr051_provision_utilities.py` gives
 * a utility accounts and a cycle but no meter reads and no bill templates, so
 * neither the bill-run door nor the charge-fee door can issue anything. Every
 * database on the box was measured: **zero issued invoices in all of them.**
 * So the end-to-end check has never actually been executed here, and a defect
 * fixed with no browser behind it is exactly what law 6 is about.
 *
 * **What this one trades away, stated plainly so nobody over-reads it:** the
 * API is a STUB in this file, so it proves nothing about the SERVER — not that
 * `documents.py` resolves the right layout, not that the switches it serves are
 * the ones the frozen page was built from. `test_us_bil_021_tc20` and the
 * python suites own that half, and the end-to-end file owns the join.
 *
 * **What it proves that no unit test can:**
 *   · the SHIPPED BYTES. `vite build` output served by `07-frontend/server.mjs`,
 *     which is the deployed join — not modules loaded unbundled by vitest.
 *   · REAL RENDERING. jsdom performs no layout, so it cannot answer whether a
 *     column is on the page or whether the page scrolls sideways at 1440px.
 *   · the page as a PERSON sees it — `innerText`, not markup. That distinction
 *     is load-bearing here: B14 rule 31's own escape puts the internal value on
 *     a `data-` attribute, so a check over the DOM STRING goes RED on a correct
 *     fix and GREEN on the breach.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *     (cd 07-frontend && npx vite build)
 *     PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *       node 10-scripts/render-checks/def2826-bill-layout.mjs
 *
 * It starts its own stub API and its own SPA server and tears both down. The
 * only precondition is `07-frontend/dist`, and it says so by name if missing.
 *
 * ── WHAT IT ASSERTS (29) ──────────────────────────────────────────────────
 *   DEF-2826 · the STANDARD layout draws the masthead, the services band and
 *     the Usage and Rate columns · the COMPACT layout draws NONE of the three,
 *     and its AMOUNT is still there (a layout suppresses DETAIL, never money) ·
 *     the quantity leaves WITH its column rather than being orphaned under the
 *     wrong heading · the LETTERHEAD layout suppresses the masthead, which is
 *     its whole purpose, and changes nothing else · the two pages are actually
 *     DIFFERENT, which is the assertion the defect was filed on.
 *   B14 rule 31 · the layout is named IN WORDS and `platform-layout-…` is
 *     nowhere in the text.
 *   DEF-2715 · no rule id, open-question id, A19 section number, backticked
 *     identifier, module path or `.py` name anywhere in the page's text; the
 *     absence says what the dash means; the two gap panels read as sentences;
 *     and the server's own words are still ON the element for support.
 *   Geometry · neither page scrolls sideways at 1440px.
 *
 * ── PROVED RED (law 7) ────────────────────────────────────────────────────
 * Pinning `layout` to `DEFAULT_BILL_LAYOUT` in `BillDocumentPage.tsx` — which
 * IS the defect, one line — and rebuilding turns the compact and letterhead
 * assertions red. Restoring it returns all 29 to green. Do the same to the
 * `billing.document.fieldAbsent` line for the DEF-2715 half.
 *
 * ⚠ **AND ONE ASSERTION IN THIS FILE WAS WRONG FIRST TIME, WHICH IS WHY IT IS
 * WORTH SAYING.** *"the utility name is gone with the band"* was written
 * against the whole BODY, and the utility's name is also in the app-shell
 * header — so it failed on a correct fix. It is scoped to the `<article>` now.
 * A check whose output cannot tell pass from fail is worse than no check.
 */
import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import { createServer } from "node:http";
import { existsSync, mkdirSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const FRONTEND = join(HERE, "..", "..", "07-frontend");
const require_ = createRequire(join(FRONTEND, "package.json"));
const { chromium } = require_("playwright-core");

if (!existsSync(join(FRONTEND, "dist", "index.html"))) {
  console.error("07-frontend/dist is missing — run `(cd 07-frontend && npx vite build)` first");
  process.exit(2);
}

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
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  console.error("no playwright chromium found (PLAYWRIGHT_BROWSERS_PATH or /opt/pw-browsers)");
  process.exit(2);
}

const API_PORT = Number(process.env.STUB_API_PORT ?? 8043);
const WEB_PORT = Number(process.env.STUB_WEB_PORT ?? 4243);
const BASE = `http://127.0.0.1:${WEB_PORT}`;
const OUT = process.env.SMOKE_OUT ?? "/tmp/def2826-bill-layout";
mkdirSync(OUT, { recursive: true });

// ── the three layouts, exactly as `documents.LAYOUT_SPECS` declares them ────
const LAYOUTS = {
  "inv-standard": {
    key: "standard-letter-v1",
    masthead: true,
    services_band: true,
    detail_columns: true,
    summary_first: false,
    stub: true,
    reserve_rows: 0,
  },
  "inv-compact": {
    key: "compact-letter-v1",
    masthead: true,
    services_band: false,
    detail_columns: false,
    summary_first: false,
    stub: true,
    reserve_rows: 0,
  },
  "inv-letterhead": {
    key: "letterhead-letter-v1",
    masthead: false,
    services_band: true,
    detail_columns: true,
    summary_first: false,
    stub: true,
    reserve_rows: 6,
  },
};

/** ⚠ COPIED VERBATIM FROM `documents._masthead`. This is the string DEF-2715 is
 *  about, and copying it rather than inventing one is the point: a check that
 *  invents mild prose cannot tell you whether the real prose reaches a clerk. */
const SERVER_WHY =
  "A19 §1.1 mastheads the bill with the utility's name; the snapshot stamps no " +
  "tenant identity, so the document cannot say who sent it. BR-BIL-030 lists " +
  "'tenant identity and branding reference' as stamped.";

/** Likewise from `documents._run_problems` — a rule id, an open question, a
 *  backticked column and a module path, which is what a clerk was reading. */
const SERVER_PROBLEM =
  "bill BL-2608-000097 was ISSUED without a printable total due. BR-BIL-035's " +
  "balance-forward figures are not stamped into `bill_payload`. TO FIX: stage 6 " +
  "(apps/billing/stages/assemble_document.py) must stamp the section OQ-117 names.";

function documentFor(id) {
  const layout = LAYOUTS[id] ?? LAYOUTS["inv-standard"];
  return {
    invoice_id: id,
    invoice_no: "BL-2608-000097",
    template_id: "tpl-1",
    template_version: 3,
    payload_version: 1,
    layout_source: `platform-layout-${layout.key}`,
    layout,
    currency: "USD",
    content_type: "text/html; charset=utf-8",
    body: "<article>rebuilt</article>",
    pdf_content_type: "application/pdf",
    pdf_page_count: 1,
    pdf_url: `/invoices/${id}/document.pdf`,
    masthead: [
      { label: "Utility", value: "Brazos Bend Utilities", absent: null },
      {
        label: "Address",
        value: "—",
        absent: { field: "utility_address", why: SERVER_WHY, br_ref: "BR-BIL-030" },
      },
    ],
    meta: [{ label: "Bill #", value: "BL-2608-000097", absent: null }],
    services: [{ label: "Services", value: "Water", absent: null }],
    groups: [
      {
        heading: "Water",
        absent: null,
        lines: [
          { description: "Volumetric", quantity: "12.5 kgal", unit_price: "3.2000", amount: "40.00" },
        ],
      },
    ],
    summary: [{ label: "Total due", value: "40.00", absent: null }],
    remarks: [],
    usage: [],
    footer: [],
    stub: [{ label: "Amount enclosed", value: "40.00", absent: null }],
    absent: [],
    pdf_unrepresentable: [
      {
        field: "pdf_text",
        why: "this bill's text contains ł — OQ-150 · BR-BIL-033 — printed as '?'",
        br_ref: "OQ-150 · BR-BIL-033",
      },
    ],
    problems: [
      {
        code: "total_due_not_printable",
        invoice_id: id,
        invoice_no: "BL-2608-000097",
        br_ref: "OQ-117 · BR-BIL-035",
        detail: SERVER_PROBLEM,
      },
    ],
    unavailable: [],
    provenance: "re_rendered_from_data_not_the_original",
    message_key: "billing.document.reRendered",
    provenance_detail: "no copy of this bill was kept when it was issued.",
    unavailable_reason: "document_not_stored",
    original_html: null,
    frozen_document: null,
    frozen_page: null,
  };
}

const json = (res, body) => {
  res.writeHead(200, { "content-type": "application/json" });
  res.end(JSON.stringify(body));
};

const stub = createServer((req, res) => {
  const path = (req.url ?? "").split("?")[0];
  if (path.endsWith("/me/permissions")) {
    return json(res, { permissions: [{ code: "reads_billing_runs", access: "Full" }] });
  }
  if (path.endsWith("/settings/company")) {
    return json(res, {
      legal_name: "Brazos Bend Utilities",
      dba_name: null,
      ein: null,
      state_utility_id: null,
      mailing_address: null,
      support_phone: null,
      support_email: null,
      website: null,
      logo_file_id: null,
      logo: null,
      has_logo: false,
      mark: { letters: "BB", background_hex: null, ink_hex: null, contrast_ratio: null },
      brand_primary_hex: null,
      brand_accent_hex: null,
      remit_to_address: null,
      remit_payable_to: null,
      service_hours: null,
    });
  }
  if (path.endsWith("/me")) {
    return json(res, { id: "u-1", email: "dana@example.test", full_name: "Dana", role: "clerk" });
  }
  const doc = path.match(/\/invoices\/([^/]+)\/document$/);
  if (doc) return json(res, documentFor(decodeURIComponent(doc[1])));
  return json(res, {});
});

await new Promise((resolve) => stub.listen(API_PORT, "127.0.0.1", resolve));

const web = spawn(process.execPath, [join(FRONTEND, "server.mjs")], {
  cwd: FRONTEND,
  env: {
    ...process.env,
    PORT: String(WEB_PORT),
    HOST: "127.0.0.1",
    API_PROXY_TARGET: `http://127.0.0.1:${API_PORT}`,
  },
  stdio: "ignore",
});

async function waitForWeb() {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    try {
      const response = await fetch(`${BASE}/api/x/me/permissions`);
      if (response.ok) return;
    } catch {
      /* not up yet */
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`the SPA server never came up on ${BASE}`);
}
await waitForWeb();

const failures = [];
const notes = [];
function check(label, ok, detail = "") {
  if (ok) notes.push(`  ok   ${label}`);
  else failures.push(`  FAIL ${label}${detail ? ` — ${detail}` : ""}`);
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

/** The page as a PERSON reads it. `innerText`, never markup — see the header. */
async function openBill(id) {
  await page.goto(`${BASE}/brazosbend/billing/bills/${id}/document`, { waitUntil: "networkidle" });
  await page.waitForTimeout(700);
  return (await page.locator("body").innerText()).replace(/\s+/g, " ");
}

try {
  // ── DEF-2826 ────────────────────────────────────────────────────────────
  const standard = await openBill("inv-standard");
  await page.screenshot({ path: join(OUT, "standard.png"), fullPage: true });
  check("standard: draws the Usage column", /\bUsage\b/i.test(standard));
  check("standard: draws the Rate column", /\bRate\b/i.test(standard));
  check("standard: draws the services band", standard.includes("Services this period"));
  check("standard: draws the masthead band", standard.includes("Who sent it"));
  check("standard: names its layout IN WORDS", standard.includes("the standard letter layout"));
  check("standard: the raw layout KEY is not on screen", !standard.includes("platform-layout-"));

  const compact = await openBill("inv-compact");
  await page.screenshot({ path: join(OUT, "compact.png"), fullPage: true });
  check("compact: NO Usage column", !/\bUsage\b/i.test(compact));
  check("compact: NO Rate column", !/\bRate\b/i.test(compact));
  check("compact: NO services band", !compact.includes("Services this period"));
  // ⚠ A LAYOUT SUPPRESSES DETAIL, NEVER MONEY. A bill that dropped its own
  // charge figure would be a far worse defect than the one being fixed.
  check("compact: the amount is STILL drawn", compact.includes("40.00"));
  check("compact: the quantity left WITH its column", !compact.includes("12.5 kgal"));
  check("compact: names the compact layout in words", compact.includes("the compact letter layout"));
  check("compact: the raw layout KEY is not on screen", !compact.includes("platform-layout-"));
  check("the two pages are actually DIFFERENT", standard !== compact);

  const letterhead = await openBill("inv-letterhead");
  await page.screenshot({ path: join(OUT, "letterhead.png"), fullPage: true });
  check("letterhead: the masthead is suppressed — its whole purpose", !letterhead.includes("Who sent it"));
  check(
    "letterhead: the utility name went with the band",
    !(await page.locator("article").innerText()).includes("Brazos Bend Utilities"),
  );
  check("letterhead: everything else stays", letterhead.includes("Services this period"));

  // ── DEF-2715 ────────────────────────────────────────────────────────────
  // SHAPES, not sentences: a check pinned to today's wording goes green the
  // moment somebody rewords the prose while leaving it prose.
  const INTERNAL = [
    [/\bBR-[A-Z]{3}-\d{3,5}(?!\d)\b/, "a rule id"],
    [/\bOQ-\d{3,5}(?!\d)\b/, "an open-question id"],
    [/A19 §/, "an A19 section number"],
    [/`[a-z_]+`/, "a backticked identifier"],
    [/apps\/billing/, "a module path"],
    [/\.py\b/, "a python file name"],
  ];
  for (const [shape, what] of INTERNAL) {
    const hit = standard.match(shape);
    check(`no ${what} anywhere in the page's text`, hit === null, hit ? hit[0] : "");
  }
  check("the absence says what the dash means", standard.includes("This bill did not record it."));
  check(
    "the run problem reads as a sentence, not a module note",
    standard.includes("went out with no amount due on it"),
  );
  check("the page-limit note reads as a sentence", standard.includes("could not be printed on the page"));
  await openBill("inv-standard");
  check(
    "the server's own words are still ON the element for support",
    (await page.locator("[data-absent-why]").count()) > 0,
  );

  // ── geometry, the half only a browser can answer ─────────────────────────
  for (const [name, id] of [
    ["standard", "inv-standard"],
    ["compact", "inv-compact"],
  ]) {
    await openBill(id);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    check(`${name}: does not scroll sideways at 1440px`, overflow <= 0, `overflow ${overflow}px`);
  }
} finally {
  await browser.close();
  web.kill();
  stub.close();
}

writeFileSync(join(OUT, "report.txt"), [...notes, ...failures].join("\n"));
console.log(notes.join("\n"));
if (failures.length > 0) {
  console.log("\n" + failures.join("\n"));
  console.log(`\n${failures.length} FAILURE(S) · screenshots in ${OUT}`);
  process.exit(1);
}
console.log(`\nall ${notes.length} assertion(s) pass · screenshots in ${OUT}`);
