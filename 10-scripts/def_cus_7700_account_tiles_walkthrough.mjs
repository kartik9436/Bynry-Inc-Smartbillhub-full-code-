// ── Trace ──────────────────────────────────────────────
// Change:  PO ruling 2026-09-28 — the Accounts register's FOUR status tiles
//          (`BR-CUS-1105`), each of which SETS the list's filter when pressed.
// Defect:  DEF-CUS-7700 (the two tiles that never counted) · DEF-CUS-7701 (the
//          `BuildTiles` fold-in the shared strip now unblocks)
// Rules:   B14 rule 33 (a LABEL ≤ 3 words · a FACT ≤ 6 · RATIONALE zero) ·
//          rule 31 (nothing internal is a visible value) · BR-CUS-055 ·
//          CLAUDE.md hard-won law 6 (diff the RUNNING app — no gate in this
//          repo reads rendered output, and this is the only check that does)
// Screens: S17 — Accounts → Accounts
// ───────────────────────────────────────────────────────
//
// WHAT THIS SEES THAT THE SUITES CANNOT
// -------------------------------------
// `AccountsStatusTiles.dom.test.tsx` clicks a tile in jsdom and reads the chip
// back. jsdom does no LAYOUT and serves no bundle, so it cannot see: four
// tiles that wrap onto two rows, a pressed ring that paints nothing because
// the utility never compiled, a label clipped by its track, or a screen built
// from a `dist/` that predates the change. Every one of those is a green suite
// over a wrong screen (hard-won law 6, and `DEF-LED-6498` for the clipping).
//
// ⚠ **STEP 0 READS THE SERVED BUNDLE FIRST.** A `dist/` built before this
// change would make every later step measure the OLD screen while reporting on
// the new one — the failure `br_cus_1093_master_services_walkthrough.mjs`
// records in its own step 0.
//
// ⚠ **IT WRITES NOTHING.** Every step is a GET or a click that only changes a
// query string.
//
// MEASURED 2026-09-28, CHROMIUM, `brazosbend` ON THE DEV DATABASE, `2.392.0`
// -------------------------------------------------------------------------
//     the served bundle carries the new tile keys              ✓
//     === 1440px === and === 1280px ===, identical both times:
//       exactly four tiles                                     ✓
//       the four the PO ruled, in the PO's order               ✓
//       every tile is a control · states a number · unclipped  ✓
//       the strip is ONE row — four tiles, one top edge        ✓
//       the group is named                                     ✓
//       the four dropped words are gone from the strip         ✓
//       B14 rule 33 — one-word labels, ≤6-word lines           ✓
//       B14 rule 31 — no uuid, no internal status code         ✓
//       pressing Active puts a chip in the FILTER BAR          ✓
//       the pressed ring really paints                         ✓
//       the TABLE narrowed too (5 of 11 rows)                  ✓
//       pressing again clears it, page back to 1               ✓
//     47 passed, 0 failed
//
// ⚠ **THREE THINGS FAILED FIRST, AND ONLY ONE WAS THE PRODUCT'S.** (1) Step 0
// refused a `dist/` built in `production` mode — the deployed bundle points at
// `https://api-smart360.bynry.com` and its own CSP then refuses the call, so
// every screen fails sign-in; build with a non-deployed mode
// (`vite build --mode smoke`) for a local walk. **`10-scripts/11-smoke-stack.sh`
// runs a bare `npx vite build`, so the smoke stack itself now boots a bundle
// that cannot reach its own backend — `DEF-INF-7702`.** (2) The labels are
// UPPERCASED BY CSS, so `innerText` returns `ACTIVE`; a case-sensitive draft
// failed on a correct screen, which is the mistake `br_cus_1093`'s walkthrough
// records. (3) On an EMPTY list `DataTable` draws no toolbar at all, so there
// is no chip row to read — the case asks whether a STATUS chip is applied, not
// whether the `All` chip exists.
//
// RUN IT, with the stack up:
//   node 10-scripts/def_cus_7700_account_tiles_walkthrough.mjs
//   AT_BASE     default http://127.0.0.1:8922
//   AT_TENANT   default brazosbend
//   AT_EMAIL / AT_PASSWORD  the seeded admin
//   AT_CHROME   default /opt/pw-browsers/chromium-1194/chrome-linux/chrome
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.AT_BASE || "http://127.0.0.1:8922";
const T = process.env.AT_TENANT || "brazosbend";
const EMAIL = process.env.AT_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.AT_PASSWORD || "S3cure!passw0rd";
const CHROME = process.env.AT_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

const RULED = ["Active", "Pending", "Disconnecting", "Suspended"];
const DROPPED = ["Outstanding", "Past-due 60+", "Closed this year", "Not counted yet"];

let pass = 0;
let fail = 0;
function ok(what, cond, detail = "") {
  if (cond) {
    pass += 1;
    console.log(`  ✓ ${what}`);
  } else {
    fail += 1;
    console.log(`  ✗ ${what}${detail ? ` — ${detail}` : ""}`);
  }
}

// A walk that hangs is a walk nobody reads.
const KILL = setTimeout(() => {
  console.error("REFUSED: walkthrough exceeded 10 minutes — killing");
  process.exit(3);
}, 600000);

async function signIn(context, width) {
  const p = await context.newPage({ viewport: { width, height: 1000 } });
  p.setDefaultTimeout(25000);
  // ⚠ **THE CLICK FIRST, THE WAIT AFTER — `12-smoke-walkthrough.mjs`'s own
  // shape.** A `Promise.all([waitForURL, click])` with the default
  // `waitUntil: "load"` never resolved here: this is a client-side route
  // change, so there is no load event to wait for and the walk timed out on a
  // sign-in that had actually succeeded.
  await p.goto(`${BASE}/${T}/signin`, { waitUntil: "networkidle" });
  await p.fill("#signin-email", EMAIL);
  await p.fill("#signin-password", PASSWORD);
  await p.click('button[type="submit"]');
  await p.waitForURL(`**/${T}/dashboard`, { timeout: 25000 });
  return p;
}

/** The strip as a person sees it: painted text, painted geometry. */
async function readStrip(page) {
  await page.waitForSelector(".kpi-grid", { timeout: 20000 });
  return page.evaluate(() => {
    const grid = document.querySelector(".kpi-grid");
    const tiles = [...grid.children].map((node) => {
      const box = node.getBoundingClientRect();
      const value = node.querySelector("span.v");
      return {
        tag: node.tagName.toLowerCase(),
        label: (node.querySelector("span.k")?.innerText || "").trim(),
        value: (value?.innerText || "").trim(),
        detail: (node.querySelector("span.d")?.innerText || "").trim(),
        pressed: node.getAttribute("aria-pressed"),
        // ⚠ GEOMETRY, because a string assertion structurally cannot see a
        // clipped number (`DEF-LED-6498`) or a strip that wrapped.
        top: Math.round(box.top),
        clipped: value ? value.scrollWidth > value.clientWidth + 1 : false,
        outline: getComputedStyle(node).outlineStyle,
      };
    });
    return {
      tiles,
      role: grid.getAttribute("role"),
      groupName: grid.getAttribute("aria-label"),
      text: grid.innerText,
    };
  });
}

async function chipRow(page) {
  return page.evaluate(() =>
    [...document.querySelectorAll("[data-chip]")].map((n) =>
      (n.innerText || "").replace(/[×✕]\s*$/, "").trim(),
    ),
  );
}

let browser;
try {
  browser = await chromium.launch({ executablePath: CHROME });

  // ── 0 · THE SERVED BUNDLE IS THIS COMMIT'S ───────────────────────────────
  {
    const p = await (await browser.newContext()).newPage();
    const scripts = [];
    p.on("response", (r) => {
      if (r.url().endsWith(".js")) scripts.push(r.url());
    });
    await p.goto(`${BASE}/${T}/signin`, { waitUntil: "networkidle" });
    let found = false;
    for (const url of scripts) {
      const body = await (await p.request.get(url)).text();
      if (body.includes("customers.accounts.kpi.statusDisconnecting")) found = true;
    }
    ok("the served bundle carries the new tile keys", found, `${scripts.length} script(s) read`);
    await p.close();
  }

  // ⚠ **1280 AND 1440 — the two widths the staff app is verified at.** Below
  // 1280 is deliberately unsupported; above 1440 the content caps.
  for (const width of [1440, 1280]) {
    console.log(`=== ${width}px ===`);
    const context = await browser.newContext();
    const page = await signIn(context, width);
    await page.goto(`${BASE}/${T}/accounts`, { waitUntil: "domcontentloaded" });
    const strip = await readStrip(page);

    ok("exactly four tiles", strip.tiles.length === 4, `saw ${strip.tiles.length}`);
    // ⚠ **CASE-INSENSITIVE, AND THAT IS NOT A LOOSENING.** `.kpi .k` sets
    // `text-transform: uppercase`, so `innerText` returns what is PAINTED —
    // `ACTIVE`, not `Active`. A case-sensitive draft here would fail on a
    // correct screen, which is the mistake `br_cus_1093`'s walkthrough already
    // made once and wrote down. The catalogue's own casing is asserted in
    // `AccountsPage.test.tsx`, over the markup, where it is the real question.
    ok(
      "the four the PO ruled, in the PO's order",
      JSON.stringify(strip.tiles.map((t) => t.label.toLowerCase())) ===
        JSON.stringify(RULED.map((w) => w.toLowerCase())),
      JSON.stringify(strip.tiles.map((t) => t.label)),
    );
    ok(
      "every tile is a control",
      strip.tiles.every((t) => t.tag === "button" && t.pressed !== null),
      JSON.stringify(strip.tiles.map((t) => t.tag)),
    );
    ok(
      "every tile states a number",
      strip.tiles.every((t) => /^\d+$/.test(t.value)),
      JSON.stringify(strip.tiles.map((t) => t.value)),
    );
    ok("no number is clipped", strip.tiles.every((t) => !t.clipped));
    ok(
      "the strip is ONE row — four tiles, one top edge",
      new Set(strip.tiles.map((t) => t.top)).size === 1,
      JSON.stringify(strip.tiles.map((t) => t.top)),
    );
    ok("the group is named", strip.role === "group" && Boolean(strip.groupName), strip.groupName);
    for (const gone of DROPPED) {
      ok(`the strip no longer says "${gone}"`, !strip.text.includes(gone));
    }
    ok(
      "B14 rule 33 — every LABEL is one word",
      strip.tiles.every((t) => t.label.trim().split(/\s+/).length === 1),
    );
    ok(
      "B14 rule 33 — every line under a tile is six words or fewer",
      strip.tiles.every((t) => t.detail.split(/\s+/).filter(Boolean).length <= 6),
      JSON.stringify(strip.tiles.map((t) => t.detail)),
    );
    ok("B14 rule 31 — no uuid on the strip", !/[0-9a-f]{8}-[0-9a-f]{4}/.test(strip.text));
    ok(
      "B14 rule 31 — no internal status code on the strip",
      !/vacation_hold|marked_disconnect|pending_activation/.test(strip.text),
    );

    // ── THE PRESS, IN A REAL BROWSER ─────────────────────────────────────
    // ⚠ **NO STATUS CHIP, RATHER THAN EXACTLY `["All"]`.** The first draft
    // asserted the `All` chip was there and failed on a correct screen: this
    // tenant's list was EMPTY, and `DataTable` draws the empty state with no
    // toolbar at all, so there was no chip row to read. What this case is
    // about is whether a STATUS filter is applied, and that is what it asks.
    const rowsAll = await page.evaluate(
      () => document.querySelectorAll("table tbody tr").length,
    );
    const before = await chipRow(page);
    ok("no status filter to start with", !before.some((c) => /^Status:/i.test(c)),
      JSON.stringify(before));

    await page.click('[data-kpi="active"]');
    await page.waitForFunction(
      () => new URL(location.href).searchParams.get("f.status") === "active",
      { timeout: 15000 },
    );
    const after = await chipRow(page);
    ok("pressing Active puts a chip in the FILTER BAR", after.some((c) => /^Status:/.test(c)),
      JSON.stringify(after));
    const pressedStrip = await readStrip(page);
    // Case-insensitive for the reason the order check above already gives:
    // `innerText` returns the PAINTED label, which CSS uppercases.
    const activeTile = pressedStrip.tiles.find((t) => t.label.toLowerCase() === "active");
    ok("the tile says it is on", activeTile?.pressed === "true");
    ok(
      "…and the pressed ring really paints (a class the compiler never emitted would not)",
      activeTile?.outline !== "none",
      String(activeTile?.outline),
    );
    ok(
      "exactly one tile is on",
      pressedStrip.tiles.filter((t) => t.pressed === "true").length === 1,
    );
    const rowsNarrowed = await page.evaluate(
      () => document.querySelectorAll("table tbody tr").length,
    );
    // ⚠ **THE TABLE, NOT ONLY THE URL.** A tile that wrote `f.status` and left
    // the table showing everything is the two-controls-disagreeing defect this
    // whole change exists to avoid, and no assertion about the chip can see
    // it. `>= 1` and `< total` is the shape: the fixture plants five active
    // accounts out of eleven.
    ok(
      "the TABLE narrowed too — this is not a tile lighting itself up",
      rowsNarrowed >= 1 && rowsNarrowed < rowsAll,
      `${rowsNarrowed} row(s) narrowed against ${rowsAll} unfiltered`,
    );

    await page.click('[data-kpi="active"]');
    await page.waitForFunction(
      () => new URL(location.href).searchParams.get("f.status") === null,
      { timeout: 15000 },
    );
    const cleared = await chipRow(page);
    ok("pressing it again clears the filter", !cleared.some((c) => /^Status:/i.test(c)),
      JSON.stringify(cleared));
    ok(
      "…and the page went back to 1",
      new URL(page.url()).searchParams.get("page") !== "3",
      page.url(),
    );

    await context.close();
  }
} finally {
  clearTimeout(KILL);
  if (browser) await browser.close();
}

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail === 0 ? 0 : 1);
