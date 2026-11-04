#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:   CR-053 task 15 — *"render checks for every screen in tasks 1–13"* —
//           over CR-053 task 9, the per-service subtotal block and its tie-out.
// Screens:  S30 → bill detail → Charges tab → *What each service cost*
// Rules:    BR-BIL-032 (drift can never be silent) · B4.4 + B4's 2026-08-11
//           ruling (Σ of the ROUNDED lines) · PO 2026-08-11 (*"Tax rates are
//           for bill not for service"*) · PO 2026-08-30 R1–R7 (*the document
//           displays what the server resolved*) · B14 rule 31 (no database id
//           is the visible value of a field) · B14 rule 32 clause 4 (no rule id
//           or internal code in clerk-facing copy) · hard-won law 6 (diff the
//           RUNNING app) · law 7 (RED first)
// Defects:  DEF-2429 (a `minimum_adjustment` line stores no service, so
//           per-service money sits in the bill-level bucket) · DEF-1931 (the
//           rule id belongs on the element, never in the sentence) ·
//           DEF-2901 (no database on this box holds an issued invoice)
// ───────────────────────────────────────────────────────
/**
 * THE PER-SERVICE SUBTOTALS AND THEIR TIE-OUT, IN A REAL BROWSER, ON THE
 * SHIPPED BUNDLE — AND WITH NO DATABASE.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * WHY THIS EXISTS BESIDE `cr053-bill-surface.mjs` RATHER THAN INSTEAD OF IT
 * ══════════════════════════════════════════════════════════════════════════
 * `cr053-bill-surface.mjs` is the END-TO-END check and it is the better
 * evidence: it drives a REAL bill through a REAL server and compares every
 * figure on the Charges tab against `GET /invoices/{id}` fetched in the same
 * run. **Nothing here replaces it and nothing here should be read as covering
 * what it covers** — the alignment, the frame, the panel order, the tax
 * authorities and the seven line fields are all its, and they stay its.
 *
 * **What it can never reach, and this file exists for exactly that.** Every
 * bill that check has ever opened TIES OUT. Its tie-out assertion is
 *
 *     String(cbs.tie_out.ties_out) === charges.tiesOut
 *
 * — the server's verdict against the screen's, which is the right assertion
 * and is satisfied by `true === "true"` on every run there has ever been. **A
 * check that only ever sees a zero delta cannot tell a working tie-out from an
 * absent one**; a screen that hard-coded `data-ties-out="true"` and dropped the
 * disagreement branch entirely would pass it, every time. This repo found
 * eleven checks of that shape in one day, which is why it is worth saying
 * plainly: the branch a clerk needs — *these lines add up to $258.28 and the
 * bill says $260.00* — has never been drawn in a browser.
 *
 * **And it cannot be reached from data.** A drifted bill is not a state the
 * product can be driven into: `invoice_lines` carries `trg_invoice_line_
 * immutable` (hard rule 4) and the engine writes lines that foot. Reaching one
 * end-to-end means corrupting a bill in a throwaway database — and there is no
 * bill to corrupt: **all 35 databases on this box hold ZERO invoices**,
 * re-measured 2026-09-01 (`DEF-2901`). So the payload is a STUB here, and the
 * stub is what makes the four never-drawn branches reachable at all.
 *
 * ── WHAT THIS FILE DELIBERATELY DOES NOT PROVE ───────────────────────────
 * Stated plainly so nobody over-reads it, and this list is the point of the
 * file having a header:
 *
 *   · **NOTHING ABOUT THE SERVER.** The API is a stub. It does not show that
 *     `_charges_by_service` groups on `invoice_lines.service_id`, that it sums
 *     Σ of the ROUNDED lines, or that its `tie_out` compares the right two
 *     figures. `06-backend/tests/test_cr053_charges_tab_backend.py` owns that
 *     half and the golden harness owns the arithmetic.
 *   · **NOTHING ABOUT WHETHER A REAL BILL CAN DRIFT**, or how often. It proves
 *     only that IF the server states a disagreement, the screen states it too.
 *   · **NOT THE JOIN.** That a real `GET /invoices/{id}` answers the shape this
 *     stub serves is `cr053-bill-surface.mjs`'s, run against a real server.
 *   · **NOT THE REST OF THE CHARGES TAB** — the lines table, the tax
 *     authorities, the due-date panel and the alignment are all covered there
 *     and are not re-asserted here.
 *
 * **What it proves that no unit test can:** the SHIPPED BYTES (`vite build`
 * output served by `07-frontend/server.mjs`, the deployed join — not modules
 * loaded unbundled by vitest); REAL RENDERING, so *"the warning is visibly a
 * warning"* is a measured background and border rather than a class name; and
 * the page as a PERSON reads it — `innerText`, never markup, which is
 * load-bearing because B14 rule 31's own escape puts the internal value on a
 * `data-` attribute, so a check over the DOM STRING goes RED on a correct fix
 * and GREEN on the breach.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *     (cd 07-frontend && npx vite build)
 *     PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *       node 10-scripts/render-checks/cr053-charges-tie-out.mjs
 *
 * It starts its own stub API and its own SPA server and tears both down. The
 * only precondition is `07-frontend/dist`, and it says so by name if missing.
 * ⚠ **REBUILD BEFORE MEASURING.** A check pointed at a stale `vite build`
 * reports failure with total confidence and no hint that it is reading the
 * wrong bytes.
 *
 * ── THE FIVE BILLS, AND WHY EACH ONE IS HERE ──────────────────────────────
 *   `ties`      the control. Water 238.60 + bill-level 19.68 = 258.28 = total.
 *   `drift`     THE ONE NOTHING HAS EVER DRAWN. The same rows against a bill
 *               claiming 260.00 — the rows add to 1.72 LESS than the bill.
 *   `noservice` `services: []`. The server refuses to write a zero-valued row
 *               for a service the bill never touched; the screen must keep that
 *               distinction rather than drawing an empty table.
 *   `minimum`   `DEF-2429` — a `minimum_adjustment` in the bill-level bucket.
 *               Seeded bills carry `tax` and nothing else, so the misfiled note
 *               has never been on a screen either.
 *   `noblock`   the server omits `charges_by_service` (one deploy behind). The
 *               page must state the absence, not white-screen on it.
 *
 * ── WHAT IT ASSERTS (44) ──────────────────────────────────────────────────
 *   THE MONEY IS THE SERVER'S · every subtotal on screen is the server's own
 *     2dp string and the 4dp stored scale is ABSENT, on all five bills.
 *   THE DISAGREEMENT IS DRAWN · `data-ties-out="false"`, BOTH figures in the
 *     sentence, `role="alert"`, and the difference between the two figures a
 *     person reads equals the server's own stated `delta` — so the screen is
 *     showing the two figures the server compared and not two others.
 *   IT IS NOT RECONCILED · the per-service and bill-level figures are
 *     BYTE-IDENTICAL on the drifted bill and the control, and the bill's own
 *     total is never substituted for the rows' sum or the other way round.
 *     That is `BR-BIL-032`'s evidence, still on the page.
 *   IT IS VISIBLY A WARNING · measured `background-color` and
 *     `border-left-color`, both DIFFERENT from the control's tie-out line.
 *     Only a browser can answer this.
 *   IT IS CONDITIONAL · the control and the drifted bill produce DIFFERENT
 *     tie-out text. This is the assertion a hard-coded verdict cannot pass, and
 *     it is `DEF-182`'s rule that a check whose output cannot distinguish pass
 *     from fail is worse than no check.
 *   B14 rule 31 · no uuid and no invoice id anywhere in the panel's TEXT.
 *   B14 rule 32 clause 4 · no rule id, open-question id, `snake_case` token,
 *     module path or `.py` name in the panel's text — and `DEF-1931`'s test on
 *     the misfiled note: the rule id is ON the element and NOT in the sentence.
 *   THE STATED ABSENCES · `services: []` says so in words and draws NO service
 *     row; an omitted block says so in words and the rest of the tab still
 *     renders.
 *   GEOMETRY · the verdict sits BELOW the figures it is about, by measured Y,
 *     and the panel does not scroll sideways at 1440px.
 *
 * ── PROVED RED (law 7) ────────────────────────────────────────────────────
 * The sabotage is the defect this file is written for, one line: make the
 * tie-out paragraph unconditional in `BillDetailPage.tsx` —
 *
 *     data-ties-out="true"  … {t("billing.bill.byServiceTiesOut")}
 *
 * which is *"a tie-out that is present, green, and cannot fail"*. Rebuild and
 * the drift half goes red while every other assertion in this file stays
 * green. The red is quoted in the commit that introduced this file.
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

const API_PORT = Number(process.env.STUB_API_PORT ?? 8047);
const WEB_PORT = Number(process.env.STUB_WEB_PORT ?? 4247);
const BASE = `http://127.0.0.1:${WEB_PORT}`;
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr053-charges-tie-out";
mkdirSync(OUT, { recursive: true });

// ── the payloads ───────────────────────────────────────────────────────────
// ⚠ THE STORED SCALE AND THE DISPLAY SCALE ARE BOTH SERVED, DELIBERATELY.
// CLAUDE.md rule 2: money is stored to 4 decimals and DISPLAYED at 2, and the
// server rounds once (`_display_money`). Serving both is what lets this file
// assert that the 4dp figure never reaches a screen — an assertion that is
// impossible if the stub only carries the figure the screen is supposed to
// draw.
const LINE = {
  id: "ln-1",
  kind: "usage",
  description: "Water usage",
  quantity: "43.000000",
  unit: "kgal",
  unit_price: "5.200000",
  amount: "223.600000",
  taxable: true,
  gl_account_id: "gl-4110",
  gl_account_code: "4110",
  gl_account_name: "Water usage",
  tariff_version_id: "tv-1",
  tariff_version_label: "Sample — Commercial water (flat) · from 2026-06-01",
  service: "water",
  tax_id: null,
  tax_authority: null,
  charge_id: null,
  charge_code: null,
  charge_name: null,
  period_start: "2026-07-01",
  period_end: "2026-07-31",
};

const WATER = {
  service: "water",
  service_name: "Water",
  line_count: 2,
  subtotal: "238.600000",
  subtotal_display: "238.60",
};

/** The bill-level bucket the seeded utility actually produces: two tax lines. */
const TAX_BUCKET = {
  line_count: 2,
  kinds: ["tax"],
  subtotal: "19.680000",
  subtotal_display: "19.68",
};

const CHARGES = {
  // ── the control: the rows foot against the bill ──────────────────────────
  ties: {
    currency: "USD",
    services: [WATER],
    bill_level: TAX_BUCKET,
    tie_out: {
      ties_out: true,
      lines_total: "258.280000",
      invoice_total: "258.280000",
      delta: "0.000000",
    },
  },
  // ── THE BRANCH NOTHING HAS EVER DRAWN ────────────────────────────────────
  // The SAME rows against a bill claiming `260.00`. The rows add to 1.72 less
  // than the bill says, and `BR-BIL-032` requires the page to say so and to
  // change neither figure.
  drift: {
    currency: "USD",
    services: [WATER],
    bill_level: TAX_BUCKET,
    tie_out: {
      ties_out: false,
      lines_total: "258.280000",
      invoice_total: "260.000000",
      delta: "-1.720000",
    },
  },
  // ── a bill with no service-bearing line ──────────────────────────────────
  noservice: {
    currency: "USD",
    services: [],
    bill_level: {
      line_count: 1,
      kinds: ["fee"],
      subtotal: "35.000000",
      subtotal_display: "35.00",
    },
    tie_out: {
      ties_out: true,
      lines_total: "35.000000",
      invoice_total: "35.000000",
      delta: "0.000000",
    },
  },
  // ── DEF-2429: per-service money in the bill-level bucket ─────────────────
  minimum: {
    currency: "USD",
    services: [WATER],
    bill_level: {
      line_count: 3,
      kinds: ["minimum_adjustment", "tax"],
      subtotal: "27.180000",
      subtotal_display: "27.18",
    },
    tie_out: {
      ties_out: true,
      lines_total: "265.780000",
      invoice_total: "265.780000",
      delta: "0.000000",
    },
  },
};

const TOTALS = {
  ties: "258.280000",
  drift: "260.000000",
  noservice: "35.000000",
  minimum: "265.780000",
  noblock: "258.280000",
};

function detailFor(id) {
  const block = CHARGES[id] ?? null;
  return {
    id: `9f1d4c62-0000-4000-8000-00000000${id === "drift" ? "0002" : "0001"}`,
    invoice_no: "BL-2608-000094",
    bill_type: "cycle",
    status: "issued",
    past_due: false,
    account_id: "acc-1",
    account_no: "A-10432",
    customer_name: "Miller, Sarah",
    cycle_label: "08-A",
    bill_run_id: null,
    service_date: "2026-07-31",
    period_start: "2026-07-01",
    period_end: "2026-07-31",
    issued_at: "2026-08-08",
    due_date: "2026-08-25",
    subtotal: "238.600000",
    tax_total: "19.680000",
    total: TOTALS[id] ?? "258.280000",
    currency: "USD",
    template_version: 1,
    lines: [LINE],
    payload_version: 1,
    has_payload: true,
    document_url: null,
    // `noblock` omits the key entirely — a server one deploy behind.
    ...(block === null ? {} : { charges_by_service: block }),
    taxes_by_authority: null,
    summary: null,
    credit_notes: [],
    rebill_of_invoice_id: null,
    corrected_by_invoice_id: null,
    adjustments: [],
    deliveries: null,
    integrity: null,
  };
}

const json = (res, body) => {
  res.writeHead(200, { "content-type": "application/json" });
  res.end(JSON.stringify(body));
};

const unmatched = new Set();
const stub = createServer((req, res) => {
  const path = (req.url ?? "").split("?")[0];
  if (path.endsWith("/me/permissions")) {
    return json(res, {
      role: "billing_clerk",
      role_name: "Billing Clerk",
      permissions: [{ code: "reads_billing_runs", label: "Reads & Billing runs", access: "Full" }],
    });
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
  const detail = path.match(/\/invoices\/([^/]+)$/);
  if (detail) return json(res, detailFor(decodeURIComponent(detail[1])));
  unmatched.add(path);
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

/**
 * Open one bill's Charges tab and read the panel AS A PERSON SEES IT.
 *
 * ⚠ **`innerText`, NEVER `innerHTML`.** B14 rule 31's own escape is to put the
 * internal value on a `data-` attribute — which is CORRECT — so a check over
 * markup goes red on a right answer and green on a wrong one.
 */
async function openCharges(id) {
  await page.goto(`${BASE}/brazosbend/billing/bills/${id}?tab=lines`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(600);
  const panel = page.locator('[data-bil="charges-by-service"]').locator("xpath=ancestor::section[1]");
  const present = (await panel.count()) > 0;
  return {
    id,
    present,
    text: present ? (await panel.innerText()).replace(/\s+/g, " ") : "",
    body: (await page.locator("body").innerText()).replace(/\s+/g, " "),
  };
}

/** The tie-out line, read three ways: its words, its verdict, and its paint. */
async function tieOut() {
  return page.evaluate(() => {
    const el = document.querySelector('[data-bil="charges-tie-out"]');
    if (el === null) return null;
    const style = getComputedStyle(el);
    return {
      text: el.innerText.replace(/\s+/g, " ").trim(),
      verdict: el.getAttribute("data-ties-out"),
      role: el.getAttribute("role"),
      background: style.backgroundColor,
      borderLeft: style.borderLeftColor,
      top: el.getBoundingClientRect().top + window.scrollY,
    };
  });
}

/** Every drawn per-service row, and the bill-level row beside them. */
async function subtotalRows() {
  return page.evaluate(() => {
    const cells = (tr) => [...tr.querySelectorAll("td")].map((td) => td.innerText.trim());
    return {
      services: [...document.querySelectorAll('[data-bil="service-subtotal"]')].map((tr) => ({
        service: tr.getAttribute("data-service"),
        cells: cells(tr),
      })),
      billLevel: (() => {
        const tr = document.querySelector('[data-bil="bill-level-subtotal"]');
        return tr === null ? null : cells(tr);
      })(),
      tableBottom: (() => {
        const table = document.querySelector('[data-bil="charges-by-service"]');
        if (table === null) return null;
        const box = table.getBoundingClientRect();
        return box.top + box.height + window.scrollY;
      })(),
    };
  });
}

/** B14 rule 31 + rule 32 clause 4, as SHAPES rather than as today's wording. */
const INTERNAL = [
  [/\bBR-[A-Z]{3}-\d{3,5}(?!\d)\b/, "rule id"],
  [/\bOQ-\d{3,5}(?!\d)\b/, "open-question id"],
  [/\bDEF-\d{3,5}(?!\d)\b/, "defect id"],
  [/\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/i, "uuid"],
  [/\b[a-z]+_[a-z_]+\b/, "snake_case token"],
  [/apps\/billing/, "module path"],
  [/\.py\b/, "python file name"],
];

try {
  // ══ 1 · THE CONTROL — the rows foot, and the money is the SERVER's ═══════
  const ties = await openCharges("ties");
  await page.screenshot({ path: join(OUT, "1-ties.png"), fullPage: true });
  check("control: the per-service panel is on the Charges tab", ties.present);

  const tiesRows = await subtotalRows();
  const tiesWater = tiesRows.services.find((row) => row.service === "water");
  check(
    "control: Water draws the SERVER's own 2dp subtotal $238.60",
    tiesWater !== undefined && tiesWater.cells.some((cell) => cell.includes("238.60")),
    JSON.stringify(tiesWater ?? null),
  );
  check(
    "control / rule 2: the 4dp stored figure 238.600000 is NOT on the screen",
    !ties.text.includes("238.600000"),
  );
  check(
    "control: the bill-level bucket states its own figure $19.68",
    tiesRows.billLevel !== null && tiesRows.billLevel.some((cell) => cell.includes("19.68")),
    JSON.stringify(tiesRows.billLevel),
  );
  check(
    "control: the bucket names its kinds IN WORDS — 'Tax', not 'tax'",
    tiesRows.billLevel !== null && tiesRows.billLevel.some((cell) => cell.includes("Tax")),
  );

  const tiesVerdict = await tieOut();
  check("control: the tie-out line is on the page", tiesVerdict !== null);
  check(
    'control: its verdict is the server\'s — "true"',
    tiesVerdict !== null && tiesVerdict.verdict === "true",
    tiesVerdict === null ? "absent" : tiesVerdict.verdict,
  );
  check(
    "control: a bill that foots is NOT announced as an alert",
    tiesVerdict !== null && tiesVerdict.role !== "alert",
    tiesVerdict === null ? "absent" : String(tiesVerdict.role),
  );
  check(
    "control: it says the rows add to the bill's total",
    tiesVerdict !== null && /add up to the bill's total/i.test(tiesVerdict.text),
    tiesVerdict === null ? "absent" : tiesVerdict.text,
  );

  // ══ 2 · THE BRANCH NOTHING HAS EVER DRAWN ════════════════════════════════
  // Everything below this line is the assertion `cr053-bill-surface.mjs`
  // cannot make, because every bill it has ever opened ties out.
  const drift = await openCharges("drift");
  await page.screenshot({ path: join(OUT, "2-drift.png"), fullPage: true });
  const driftVerdict = await tieOut();
  const driftRows = await subtotalRows();

  check("drift: the panel is still drawn on a bill that does not foot", drift.present);
  check(
    'drift: the verdict on screen is the server\'s — "false"',
    driftVerdict !== null && driftVerdict.verdict === "false",
    driftVerdict === null ? "absent" : String(driftVerdict.verdict),
  );
  check(
    "drift: the sentence names what the ROWS add to — $258.28",
    driftVerdict !== null && driftVerdict.text.includes("$258.28"),
    driftVerdict === null ? "absent" : driftVerdict.text,
  );
  check(
    "drift: the sentence names what the BILL says — $260.00",
    driftVerdict !== null && driftVerdict.text.includes("$260.00"),
    driftVerdict === null ? "absent" : driftVerdict.text,
  );
  check(
    "drift: it says in words that nothing here changes either figure",
    driftVerdict !== null && /changes either figure/i.test(driftVerdict.text),
    driftVerdict === null ? "absent" : driftVerdict.text,
  );
  check(
    "drift: a disagreement is ANNOUNCED — role=alert, so it is not a quiet hint",
    driftVerdict !== null && driftVerdict.role === "alert",
    driftVerdict === null ? "absent" : String(driftVerdict.role),
  );

  // ⚠ THE ARITHMETIC ASSERTION, AND IT IS THE ONE THAT MATTERS. Two figures
  // being PRESENT proves nothing — a screen could print any two. The
  // difference between the two figures a person actually reads must equal the
  // `delta` the server stated, or the page is comparing two other numbers.
  const drawn = driftVerdict === null ? [] : [...driftVerdict.text.matchAll(/\$([\d,]+\.\d{2})/g)]
    .map((match) => Number(match[1].replace(/,/g, "")));
  const serverDelta = Math.abs(Number(CHARGES.drift.tie_out.delta));
  check(
    "drift: the two figures a person reads differ by the SERVER's own delta (1.72)",
    drawn.length === 2 && Math.abs(Math.abs(drawn[0] - drawn[1]) - serverDelta) < 0.005,
    `drawn=[${drawn.join(", ")}] serverDelta=${serverDelta}`,
  );

  // ⚠ NOT RECONCILED — `BR-BIL-032`'s evidence is still on the page. The
  // figures on the drifted bill must be BYTE-IDENTICAL to the control's: a
  // screen that quietly moved 1.72 anywhere to make the column foot would
  // destroy exactly what the rule exists to surface.
  const driftWater = driftRows.services.find((row) => row.service === "water");
  check(
    "drift: the per-service subtotal is UNTOUCHED by the disagreement — still $238.60",
    driftWater !== undefined &&
      JSON.stringify(driftWater.cells) === JSON.stringify(tiesWater?.cells),
    `${JSON.stringify(driftWater?.cells)} vs ${JSON.stringify(tiesWater?.cells)}`,
  );
  check(
    "drift: the bill-level subtotal is UNTOUCHED too — still $19.68",
    JSON.stringify(driftRows.billLevel) === JSON.stringify(tiesRows.billLevel),
    `${JSON.stringify(driftRows.billLevel)} vs ${JSON.stringify(tiesRows.billLevel)}`,
  );
  check(
    "drift: the bill's own total is NOT substituted into a subtotal cell",
    driftWater !== undefined && !driftWater.cells.some((cell) => cell.includes("260.00")),
    JSON.stringify(driftWater?.cells),
  );
  check(
    "drift / rule 2: no 4dp figure reaches the panel (238.600000 · 260.000000 · 1.720000)",
    !/\d\.\d{4,}/.test(drift.text),
    (drift.text.match(/\S*\d\.\d{4,}\S*/) ?? [""])[0],
  );

  // ⚠ VISIBLY A WARNING. A class name proves nothing — B14 rule 21's own
  // migration clause means a utility written in a file that is not on
  // `route-b-migrated.txt` renders as NOTHING while every `toContain("flex")`
  // assertion passes. Only a browser can answer whether the paint changed.
  check(
    "drift: the line is PAINTED differently from the control — measured background",
    driftVerdict !== null &&
      tiesVerdict !== null &&
      driftVerdict.background !== tiesVerdict.background,
    `${driftVerdict?.background} vs ${tiesVerdict?.background}`,
  );
  check(
    "drift: and its left border is a different colour from the control's",
    driftVerdict !== null &&
      tiesVerdict !== null &&
      driftVerdict.borderLeft !== tiesVerdict.borderLeft,
    `${driftVerdict?.borderLeft} vs ${tiesVerdict?.borderLeft}`,
  );

  // ⚠ THE ASSERTION A HARD-CODED VERDICT CANNOT PASS (DEF-182). Everything
  // above could in principle be satisfied by a screen that always drew the
  // drift wording; everything in section 1 by one that always drew the
  // agreement. Only the pair, DIFFERING, proves the branch is live.
  check(
    "the tie-out is CONDITIONAL — the two bills produce different verdicts",
    driftVerdict !== null && tiesVerdict !== null && driftVerdict.text !== tiesVerdict.text,
    `"${driftVerdict?.text}" vs "${tiesVerdict?.text}"`,
  );

  // ⚠ THE VERDICT FOLLOWS THE FIGURES IT IS ABOUT. jsdom performs no layout,
  // so nothing but a browser can say the sentence is below the table rather
  // than above it, where it would read as a heading.
  check(
    "drift: the verdict sits BELOW the figures it is about, by measured Y",
    driftVerdict !== null &&
      driftRows.tableBottom !== null &&
      driftVerdict.top >= driftRows.tableBottom - 1,
    `verdict ${driftVerdict?.top} vs table bottom ${driftRows.tableBottom}`,
  );

  for (const [shape, what] of INTERNAL) {
    const hit = drift.text.match(shape);
    check(`drift / B14 rules 31–32: no ${what} in the panel's text`, hit === null, hit ? hit[0] : "");
  }

  // ══ 3 · A BILL WITH NO SERVICE-BEARING LINE ══════════════════════════════
  const none = await openCharges("noservice");
  await page.screenshot({ path: join(OUT, "3-noservice.png"), fullPage: true });
  const noneRows = await subtotalRows();
  check(
    "no service: NO zero-valued service row is invented",
    noneRows.services.length === 0,
    `${noneRows.services.length} row(s)`,
  );
  check(
    "no service: it SAYS so in a sentence rather than drawing an empty table",
    /No charge on this bill belongs to a service/i.test(none.text),
    none.text.slice(0, 160),
  );
  check(
    "no service: the money is still on the page, in the bill-level bucket ($35.00)",
    noneRows.billLevel !== null && noneRows.billLevel.some((cell) => cell.includes("35.00")),
    JSON.stringify(noneRows.billLevel),
  );

  // ══ 4 · DEF-2429 — per-service money in the bill-level bucket ════════════
  const minimum = await openCharges("minimum");
  await page.screenshot({ path: join(OUT, "4-minimum.png"), fullPage: true });
  const misfiled = await page.evaluate(() => {
    const el = document.querySelector('[data-bil="minimum-misfiled"]');
    if (el === null) return null;
    return {
      text: el.innerText.replace(/\s+/g, " ").trim(),
      role: el.getAttribute("role"),
      ref: el.getAttribute("data-br-ref"),
    };
  });
  check("DEF-2429: the misfiled-minimum note is drawn when the bucket holds one", misfiled !== null);
  check(
    "DEF-2429: it says where the money belongs and that the TOTAL is unaffected",
    misfiled !== null && /total is unaffected/i.test(misfiled.text),
    misfiled === null ? "absent" : misfiled.text,
  );
  check(
    "DEF-2429: the bucket names 'Minimum bill adjustment' in words, not the stored kind",
    minimum.text.includes("Minimum bill adjustment") && !/minimum_adjustment/.test(minimum.text),
  );
  // DEF-1931 — the rule id is ON the element for support and NOT in the
  // sentence a clerk reads. Both halves, because either alone passes wrongly.
  check(
    "DEF-1931: the rule id is ON the element for support",
    misfiled !== null && /BR-RAT-028/.test(misfiled.ref ?? ""),
    misfiled === null ? "absent" : String(misfiled.ref),
  );
  check(
    "DEF-1931 / B14 rule 32 clause 4: and it is NOT in the sentence",
    misfiled !== null && !/BR-|DEF-/.test(misfiled.text),
    misfiled === null ? "absent" : misfiled.text,
  );

  // ══ 5 · THE SERVER OMITS THE BLOCK — one deploy behind ═══════════════════
  const noblock = await openCharges("noblock");
  await page.screenshot({ path: join(OUT, "5-noblock.png"), fullPage: true });
  check(
    "omitted block: the page does NOT white-screen — the lines table still renders",
    /Water usage/.test(noblock.body),
    noblock.body.slice(0, 160),
  );
  check(
    "omitted block: the absence is STATED in words",
    /Not broken down by service/i.test(noblock.body),
    noblock.body.slice(0, 200),
  );
  check(
    "omitted block: no tie-out verdict is invented where there is none to state",
    (await tieOut()) === null,
  );

  // ══ 6 · geometry, the half only a browser can answer ═════════════════════
  await openCharges("drift");
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  check("the Charges tab does not scroll sideways at 1440px", overflow <= 0, `overflow ${overflow}px`);
} finally {
  await browser.close();
  web.kill();
  stub.close();
}

if (unmatched.size > 0) {
  // Not a failure: the shell asks for things this stub does not model. It is
  // PRINTED because a screen quietly degrading on a 404 is how a check goes
  // green over a page that a person would call broken.
  notes.push(`  note the stub did not model: ${[...unmatched].join(" · ")}`);
}

writeFileSync(join(OUT, "report.txt"), [...notes, ...failures].join("\n"));
console.log(notes.join("\n"));
if (failures.length > 0) {
  console.log("\n" + failures.join("\n"));
  console.log(`\n${failures.length} FAILURE(S) · screenshots in ${OUT}`);
  process.exit(1);
}
console.log(`\nall ${notes.length} assertion(s) pass · screenshots in ${OUT}`);
