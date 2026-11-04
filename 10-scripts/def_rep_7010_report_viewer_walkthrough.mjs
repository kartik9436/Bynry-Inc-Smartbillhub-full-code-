// ── Trace ──────────────────────────────────────────────
// Change:  DEF-REP-7010 (the services column) · DEF-REP-7011 (the header
//          block) · DEF-REP-7012 (the filter row) · DEF-REP-7013 (the KPI
//          band) — the five changes the Product Owner asked for after looking
//          at the Billing Register on the deployed build `v2.380.3`, screen
//          `RPT-02`, `/{tenant}/reports/billing-register`.
// Rules:   PO definition of done, verbatim: *"everything should be executed
//          based on actual code, and rules that we place, also ensure you do
//          web walkthorugh before you sign off the user story or build"* ·
//          hard-won law 6 (no gate in this repo looks at rendered output) ·
//          hard-won law 7 clause 3 (a check's output must distinguish pass
//          from fail to a READER, not merely to an exit code) ·
//          B14 rule 44 · rule 43 · rule 33 · rule 31.
// ───────────────────────────────────────────────────────
//
// WHAT THIS PROVES THAT A UNIT TEST CANNOT.
//
//  1 · **THE PRIZE IS A ROW COUNT AND ROW COUNTS ARE GEOMETRY.** jsdom's
//      `getBoundingClientRect` is all zeroes, so no vitest case in this repo
//      can say *twenty-two rows fit*. This measures it, in a real browser, at
//      a stated viewport, and prints the number beside the target.
//  2 · **THE FOUR FILTER LABELS ARE LEVEL.** *Level* is a pixel fact. Before
//      this change `From`/`To` sat at y=289 and `Bill type`/`Service` at
//      y=317, because `.fin-params` aligns on `flex-end` and a `Today` button
//      under the box made two of the four fields taller.
//  3 · **BOTH HALVES OF THE SERVICES RULE, ON TWO REAL TENANTS.** A six-
//      service utility collapses to one line; a mixed book draws chips per
//      row. A rule proved in one direction only is half proved.
//  4 · **BOTH KINDS OF ZERO, SIDE BY SIDE.** A metered `0 kgal` is drawn and a
//      counted `0 cart` is not — on two rows of one screen, so the screenshot
//      is the argument.
//
// ⚠ **EVERY NUMBER IS PRINTED BESIDE ITS CHECK** and every viewport is stated.
// *"Rows visible"* is meaningless without the height it was counted at, and
// the Product Owner's own figure of 13 was measured at 1440×1400 — which is
// what makes 22 comparable to it rather than a different number about a
// different window.
//
// USAGE
//   BASE=http://127.0.0.1:8191 \
//   TENANT=billnarrow-six EMAIL=owner@billnarrow-six.test \
//   MIXED_TENANT=brazosbend MIXED_EMAIL=dana@brazosbendutilities.com \
//   node 10-scripts/def_rep_7010_report_viewer_walkthrough.mjs
//
// ⚠ **IT NEEDS TWO TENANTS AND SAYS SO RATHER THAN PASSING QUIETLY.** The
// collapse half needs a book where every bill carries the same services and
// the chips half needs one where they differ; a single-tenant run reports the
// missing half as UNPROVABLE, which is law 7's fifth shape (a check reporting
// zero over a scope it silently excludes).
const { existsSync, readdirSync, mkdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join, dirname } = await import("node:path");
const { fileURLToPath } = await import("node:url");

const here = dirname(fileURLToPath(import.meta.url));
const requireFrontend = createRequire(join(here, "..", "07-frontend", "package.json"));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8191";
const TENANT = process.env.TENANT ?? "billnarrow-six";
const EMAIL = process.env.EMAIL ?? "owner@billnarrow-six.test";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const MIXED_TENANT = process.env.MIXED_TENANT ?? "brazosbend";
const MIXED_EMAIL = process.env.MIXED_EMAIL ?? "dana@brazosbendutilities.com";
const OUT = process.env.OUT ?? "/tmp/def-rep-7010";
mkdirSync(OUT, { recursive: true });

/** The Product Owner's own viewport. 13 rows were counted here before the
 *  change and 22 after; any other height makes the two numbers unrelated. */
const PO_VIEWPORT = { width: 1440, height: 1400 };
const ROW_TARGET = 22;

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
  throw new Error(
    "no chromium found — PLAYWRIGHT_BROWSERS_PATH is not set and /opt/pw-browsers has none",
  );
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const say = (...parts) => console.log(...parts);
let failures = 0;
let unprovable = 0;
function check(label, ok, detail = "") {
  say(`${ok ? "PASS" : "FAIL"}  ${label}${detail === "" ? "" : ` — ${detail}`}`);
  if (!ok) failures += 1;
}
function cannot(label, why) {
  say(`CANNOT ${label} — ${why}`);
  unprovable += 1;
}

async function signIn(tenant, email, viewport) {
  const page = await browser.newPage({ viewport });
  await page.goto(`${BASE}/${tenant}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", email);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
  return page;
}

/** Open a report and WAIT FOR A ROW. A fixed sleep photographed the skeleton
 *  and reported zero rows over a screen that draws thirty-nine — a check whose
 *  answer depends on the machine's mood. */
async function openReport(page, tenant, path) {
  await page.goto(`${BASE}/${tenant}${path}`, { waitUntil: "networkidle" });
  await page
    .waitForFunction(() => document.querySelectorAll("tbody tr").length > 0, { timeout: 30000 })
    .catch(() => undefined);
  await page.waitForTimeout(700);
}

function measure() {
  const rows = [...document.querySelectorAll("tbody tr")];
  const vh = window.innerHeight;
  let visible = 0;
  for (const row of rows) {
    const box = row.getBoundingClientRect();
    if (box.top >= 0 && box.bottom <= vh && box.height > 0) visible += 1;
  }
  const first = rows[0];
  const band = document.querySelector(".kpi-grid");
  const line = document.querySelector("[data-services-line]");
  return {
    rows: rows.length,
    visible,
    firstTop: first ? Math.round(first.getBoundingClientRect().top) : null,
    rowHeight:
      rows.length > 1
        ? Math.round(rows[1].getBoundingClientRect().top - rows[0].getBoundingClientRect().top)
        : null,
    bandHeight: band ? Math.round(band.getBoundingClientRect().height) : null,
    servicesLine: line ? line.innerText.replace(/\s+/g, " ").trim() : null,
    chipRows: document.querySelectorAll("tbody [data-testid='service-chips']").length,
    heads: [...document.querySelectorAll("thead th")].map((th) => (th.textContent ?? "").trim()),
    labelTops: [...document.querySelectorAll(".fin-params .field > label")].map((label) => ({
      words: (label.textContent ?? "").trim(),
      y: Math.round(label.getBoundingClientRect().top),
    })),
    rollup: (document.querySelector(".fin-rollup")?.textContent ?? "").replace(/\s+/g, " ").trim(),
    kickers: [...document.querySelectorAll("[data-kicker]")].map((k) => (k.textContent ?? "").trim()),
    grainNodes: document.querySelectorAll("[data-grain]").length,
    cells: [...document.querySelectorAll("tbody tr")]
      .slice(0, 4)
      .map((row) => [...row.querySelectorAll("td")].map((td) => td.innerText.replace(/\s+/g, " ").trim())),
  };
}

// ═══════════════════════════════════════════════════════════════════════════
// 1 · THE UNIFORM BOOK — the screen the Product Owner photographed
// ═══════════════════════════════════════════════════════════════════════════
say(`\n══════════ ${TENANT} · ${PO_VIEWPORT.width}×${PO_VIEWPORT.height} (the PO's own viewport) ══════════`);
{
  const page = await signIn(TENANT, EMAIL, PO_VIEWPORT);
  await openReport(page, TENANT, "/reports/billing-register");
  const seen = await page.evaluate(measure);
  await page.screenshot({ path: `${OUT}/uniform-1440x1400.png` });

  check(
    `the register draws rows at all (${seen.rows} served)`,
    seen.rows > 0,
    "a zero below cannot be told from a broken screen",
  );
  check(
    `${ROW_TARGET} rows fit — counted, not estimated`,
    seen.visible >= ROW_TARGET,
    `${seen.visible} fully visible at ${PO_VIEWPORT.width}×${PO_VIEWPORT.height}; ` +
      `first row top ${seen.firstTop}px, row height ${seen.rowHeight}px, KPI band ${seen.bandHeight}px ` +
      `(before this change: 13 visible, top 634px, row 59px, band 114px)`,
  );

  // ── DEF-REP-7010 · the collapsed line ──────────────────────────────────
  check(
    "every row agrees → ONE services line above the table",
    seen.servicesLine !== null,
    seen.servicesLine ?? "no [data-services-line] on the page",
  );
  check(
    "…and SERVICES is not a column",
    !seen.heads.some((head) => /^SERVICES/i.test(head)),
    `heads: ${seen.heads.join(" | ")}`,
  );
  check(
    "…and the services are CHIPS, not words joined by dots",
    !/electric · fire/i.test(await page.evaluate(() => document.body.innerText)),
    "the old cell read `electric · fire · gas · sewer · trash · water` on all 41 rows",
  );

  // ── DEF-REP-7010 · the usage cell ──────────────────────────────────────
  const usage = seen.cells[0]?.[4] ?? "";
  check(
    "a counted zero is gone from the usage cell",
    !/\b0 cart\b/.test(usage) && !/\b0 connection\b/.test(usage),
    `row 1 usage: ${usage} (before: \`0 cart · 40 ccf · 0 connection · 800 kWh · 15.2 kgal\`)`,
  );
  const withCart = seen.cells.find((row) => /\d+ cart/.test(row[4] ?? ""));
  if (withCart === undefined) {
    cannot(
      "a NON-ZERO count survives",
      "no row in the first four carries a cart count; seed one or widen the slice",
    );
  } else {
    check("a NON-ZERO count survives — `1 cart` is what the bill charged for", true, withCart[4]);
  }

  // ── DEF-REP-7011 · the header is two lines ─────────────────────────────
  check(
    "no `REPORT` kicker over a report being read",
    seen.kickers.length === 0,
    `kickers on screen: ${JSON.stringify(seen.kickers)}`,
  );
  check(
    "the window, the basis and the grain are ONE roll-up line",
    /One row per bill/.test(seen.rollup) && /Posting date/.test(seen.rollup),
    seen.rollup,
  );
  check(
    "…and the grain is not ALSO drawn on its own line",
    seen.grainNodes === 1,
    `${seen.grainNodes} [data-grain] nodes`,
  );

  // ── DEF-REP-7012 · one filter row, labels level ────────────────────────
  const tops = [...new Set(seen.labelTops.map((one) => one.y))];
  check(
    "all four filter labels sit on ONE baseline",
    seen.labelTops.length === 4 && tops.length === 1,
    JSON.stringify(seen.labelTops) + " (before: From/To 289, Bill type/Service 317)",
  );

  // ── DEF-REP-7013 · the band is compact and the empty tile stays ────────
  check(
    "the KPI band is shorter than it was",
    (seen.bandHeight ?? 999) < 114,
    `${seen.bandHeight}px against 114px`,
  );
  check(
    "…and the tile with no figure still says so — the PO kept it on purpose",
    /Not counted yet/.test(await page.evaluate(() => document.body.innerText)),
    "`Keep the empty one — it is honest`",
  );
  await page.close();
}

// ═══════════════════════════════════════════════════════════════════════════
// 2 · THE MIXED BOOK — the other half of the rule
// ═══════════════════════════════════════════════════════════════════════════
say(`\n══════════ ${MIXED_TENANT} · the book whose rows DIFFER ══════════`);
{
  const page = await signIn(MIXED_TENANT, MIXED_EMAIL, PO_VIEWPORT);
  await openReport(page, MIXED_TENANT, "/reports/billing-register?f.from=2026-08-01&f.to=2026-08-31");
  const seen = await page.evaluate(measure);
  await page.screenshot({ path: `${OUT}/mixed-1440x1400.png` });

  if (seen.rows === 0) {
    cannot("the chips-per-row half", `${MIXED_TENANT} served no rows in August 2026`);
  } else if (seen.servicesLine !== null) {
    cannot(
      "the chips-per-row half",
      `${MIXED_TENANT}'s rows all carry the same services, so this book collapses too — ` +
        "seed a bill with a different service set",
    );
  } else {
    check("rows that differ → NO line above the table", seen.servicesLine === null);
    check(
      "…and SERVICES is a column again",
      seen.heads.some((head) => /^SERVICES/i.test(head)),
      `heads: ${seen.heads.join(" | ")}`,
    );
    check(
      "…drawn as chips, one set per row",
      seen.chipRows === seen.rows,
      `${seen.chipRows} chip groups over ${seen.rows} rows`,
    );
  }

  // ── The two kinds of zero, on one screen ───────────────────────────────
  await openReport(
    page,
    MIXED_TENANT,
    "/reports/billing-register?f.from=2026-08-01&f.to=2026-08-31&q=BL-2608-900",
  );
  const zeros = await page.evaluate(measure);
  await page.screenshot({ path: `${OUT}/two-kinds-of-zero-1440x1400.png` });
  // ⚠ **SEARCH THE WHOLE ROW, NOT A COLUMN INDEX.** The usage cell is index 4
  // when the services column has collapsed and index 5 when it has not — and
  // it has not, on this book. A fixed index reported the metered zero
  // UNPROVABLE over a screen that draws it perfectly (law 7's *looking at the
  // wrong thing*), which is how this line came to be written.
  const measuredZero = zeros.cells.find((row) => /(^|\s)0 kgal\b/.test(row.join(" ")));
  const droppedCount = zeros.cells.find((row) => /TRASH/i.test(row.join(" ")));
  if (measuredZero === undefined) {
    cannot(
      "the metered zero",
      "no row in this slice reads `0 kgal` — the fixture that seeds it is " +
        "`10-scripts/def_rep_7010_seed_two_kinds_of_zero.py`",
    );
  } else {
    check("a meter that READ ZERO is still drawn — `0 kgal`", true, measuredZero.join(" | "));
  }
  if (droppedCount === undefined) {
    cannot("the counted zero beside it", "no row in this slice carries a TRASH chip");
  } else {
    check(
      "…on a bill that carries TRASH, whose cart count is not drawn",
      !/\b0 cart\b/.test(droppedCount.join(" ")),
      droppedCount.join(" | "),
    );
  }
  await page.close();
}

// ═══════════════════════════════════════════════════════════════════════════
// 3 · THE NEIGHBOURS — the cell change is a KIND, so it reaches every report
// ═══════════════════════════════════════════════════════════════════════════
say(`\n══════════ the neighbours — nothing else moved ══════════`);
{
  const page = await signIn(TENANT, EMAIL, PO_VIEWPORT);
  for (const path of [
    "/reports/ar-aging",
    "/reports/payments-by-method",
    "/reports/revenue-by-service-rate",
  ]) {
    await openReport(page, TENANT, path);
    const seen = await page.evaluate(measure);
    await page.screenshot({ path: `${OUT}/neighbour${path.replace(/\//g, "-")}.png` });
    check(
      `${path} still draws rows`,
      seen.rows > 0,
      `${seen.rows} rows; first: ${JSON.stringify(seen.cells[0] ?? [])}`,
    );
    check(
      `${path} grows no services line of its own`,
      seen.servicesLine === null,
      seen.servicesLine ?? "",
    );
  }
  await page.close();
}

say(`\n${failures} FAILED · ${unprovable} UNPROVABLE · shots in ${OUT}`);
await browser.close();
process.exit(failures === 0 ? 0 : 1);
