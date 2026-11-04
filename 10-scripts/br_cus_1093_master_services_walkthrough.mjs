// ── AN OWNER'S ACCOUNT, ON THE SCREEN THE PRODUCT OWNER REPORTED ───────────
//
// `BR-CUS-1093` (a master account takes its utility services from its premises)
// and `DEF-CUS-6295` (a correct absence that never says why), walked in a real
// browser on the Accounts register — **the screen the report came from**.
//
// **WHY IT EXISTS.** No gate in this repository reads rendered output
// (hard-won law 6), and the thing being fixed is a CELL. The backend suite can
// prove `service_codes_for` answers `['water']`; only a browser can prove the
// register draws a water square on that row instead of the words the Product
// Owner photographed. And the `DEF-CUS-6295` sentence exists ONLY on screen —
// a test that reads a catalogue string proves the string, never that a clerk
// meets it.
//
// **THE TWO ROWS IT IS POINTED AT** are seeded by
// `10-scripts/def_cus_6295_seed_master_accounts.py`, which must be run first:
//
//   · `AC-2026-00052` — `77 Owner Way`, the building offers WATER, nothing
//     shared, so the account holds NO service agreement. Before this change the
//     cell read *No services*. It must now draw the water square.
//   · `AC-2026-00053` — `79 Owner Way`, `services_available` is NULL because
//     nobody was ever asked. It must read **No services at this address**, and
//     must NOT read the bare *No services* an ordinary account gets.
//
// ⚠ **IT REFUSES A STALE BUILD.** Nothing on the page says how old the bundle
// is, and `tsc`, the suites and every gate are green either way because none of
// them look at `dist/`. Step 0 reads the new sentence out of the served
// JavaScript before asserting anything about a screen.
//
// ⚠ **IT WRITES NOTHING.** Every step is a GET. The seeder is the half that
// writes, and it is a separate file for that reason.
//
// ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING** — a mid-run reseed
// looks exactly like a broken screen. `proof-db.sh clone` gives you a private
// one.
//
// MEASURED 2026-09-23, CHROMIUM, `brazosbend` ON A PRIVATE CLONE, v2.345.0
// ------------------------------------------------------------------------
//     the served bundle carries the new sentence               ✓
//     === 1440px === and === 1280px ===, identical both times:
//       AC-2026-00052: the Services cell draws WATER           ✓
//       AC-2026-00052: and it no longer says No services       ✓
//       AC-2026-00052: exactly one chip                        ✓
//       AC-2026-00052: the row is marked as the owner's account ✓
//       AC-2026-00053: the empty cell NAMES THE ADDRESS        ✓
//       AC-2026-00053: no chip is invented                     ✓
//       AC-2026-00053: and it explains nothing (rule 33)       ✓
//       AC-2026-00052: the account's own page shows Water too  ✓
//     23 passed, 0 failed
//
// ⚠ **THE FIRST RUN FAILED THE LAST ASSERTION ON A CORRECT SCREEN**, on both
// widths, and it is worth the four lines: the header's chip is UPPERCASED BY
// CSS, `innerText` returns what is painted, and the draft tested `/Water/`.
// The screen read `WATER` and was right. A check whose output cannot tell a
// right screen from a wrong one is worse than no check — so the assertion is
// case-insensitive now and says why at the call site.
//
//   MA_BASE     default http://127.0.0.1:8912
//   MA_TENANT   default brazosbend
//   MA_EMAIL / MA_PASSWORD  the seeded owner
//   MA_CHROME   default /opt/pw-browsers/chromium-1194/chrome-linux/chrome
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.MA_BASE || "http://127.0.0.1:8912";
const T = process.env.MA_TENANT || "brazosbend";
const EMAIL = process.env.MA_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.MA_PASSWORD || "S3cure!passw0rd";
const CHROME = process.env.MA_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

const WITH_WATER = "AC-2026-00052";
const NOTHING_RECORDED = "AC-2026-00053";
const SENTENCE = "No services at this address";

let pass = 0;
let fail = 0;
const failures = [];
function ok(what, cond, detail = "") {
  if (cond) {
    pass += 1;
    console.log(`  ✓ ${what}`);
  } else {
    fail += 1;
    failures.push(what);
    console.log(`  ✗ ${what}${detail ? ` — ${detail}` : ""}`);
  }
}

// ⚠ A HARD TIMEOUT ON THE WHOLE RUN — a walk that hangs is a walk nobody reads.
const KILL = setTimeout(() => {
  console.error("REFUSED: walkthrough exceeded 10 minutes — killing");
  process.exit(3);
}, 600000);

async function signIn(context, width) {
  const p = await context.newPage({ viewport: { width, height: 1400 } });
  p.setDefaultTimeout(25000);
  await p.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
  await p.fill("#signin-email", EMAIL);
  await p.fill("#signin-password", PASSWORD);
  await Promise.all([
    p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
    p.click('button[type="submit"]'),
  ]);
  return p;
}

/** The row whose identity cell names `accountNo`, as the DOM holds it. */
async function rowFor(page, accountNo) {
  await page.waitForSelector("table tbody tr", { timeout: 20000 });
  return page.evaluate((no) => {
    const tr = [...document.querySelectorAll("table tbody tr")].find((r) =>
      (r.innerText || "").includes(no),
    );
    if (!tr) return null;
    const cells = [...tr.querySelectorAll("td")].map((td) => ({
      text: (td.innerText || "").trim(),
      // The chips are `role="img"` with the service NAME as the accessible
      // name — read that, never the letter, because the letter is the same
      // for Sewer, Solar and Storm water.
      chips: [...td.querySelectorAll('[role="img"]')].map((n) => n.getAttribute("aria-label")),
    }));
    return { text: tr.innerText, cells };
  }, accountNo);
}

let browser;
try {
  browser = await chromium.launch({ executablePath: CHROME });

  // ── 0 · THE SERVED BUNDLE IS THIS COMMIT'S ───────────────────────────────
  // The new catalogue key is the marker: a bundle built before this change
  // cannot contain the sentence, and every other check below would then be
  // measuring the old screen while reporting on the new one.
  {
    const context = await browser.newContext();
    const p = await context.newPage();
    const assets = [];
    p.on("response", (r) => {
      if (/\/assets\/.*\.js$/.test(new URL(r.url()).pathname)) assets.push(r);
    });
    await p.goto(`${BASE}/${T}/signin`, { waitUntil: "networkidle" });
    let found = false;
    for (const r of assets) {
      const body = await r.text().catch(() => "");
      if (body.includes(SENTENCE)) found = true;
    }
    ok(
      "the served bundle carries the new sentence (not a stale dist/)",
      found,
      `looked in ${assets.length} bundle(s) — rebuild with \`npx vite build\` and restart server.mjs`,
    );
    await context.close();
  }

  // B14 rule 36: a STAFF screen is verified at 1280 AND 1440, and at nothing
  // narrower. The same assertions at both, because a cell that fits at 1440 and
  // wraps at 1280 changes a row's height on every page of the register.
  for (const width of [1440, 1280]) {
    console.log(`\n═══ the Accounts register at ${width}px ═══`);
    const context = await browser.newContext();
    const page = await signIn(context, width);

    // ── 1 · THE PO's CASE — a master at a WATER building draws the chip ─────
    await page.goto(`${BASE}/${T}/accounts?q=${WITH_WATER}`, { waitUntil: "networkidle" });
    const water = await rowFor(page, WITH_WATER);
    ok(`${WITH_WATER} is on the register`, water !== null);
    if (water !== null) {
      const chips = water.cells.flatMap((c) => c.chips).filter(Boolean);
      ok(
        `${WITH_WATER}: the Services cell draws WATER (BR-CUS-1093)`,
        chips.includes("Water"),
        JSON.stringify(chips),
      );
      // ⚠ THE NEGATIVE IS THE ONE THAT WOULD HAVE CAUGHT THE DEFECT. The row
      // read *No services* for as long as the rule was unwritten, and a check
      // that only looks for the chip passes on a screen showing both.
      ok(
        `${WITH_WATER}: and it no longer says No services`,
        !water.text.includes("No services"),
        JSON.stringify(water.text),
      );
      // The building offers exactly one service, so exactly one chip — a cell
      // drawing two would mean the read had picked up something else.
      ok(`${WITH_WATER}: exactly one chip`, chips.length === 1, JSON.stringify(chips));
      ok(
        `${WITH_WATER}: the row is marked as the owner's account`,
        water.text.includes("Master"),
        JSON.stringify(water.text),
      );
    }

    // ── 2 · THE STATED ABSENCE — `DEF-CUS-6295` ────────────────────────────
    await page.goto(`${BASE}/${T}/accounts?q=${NOTHING_RECORDED}`, { waitUntil: "networkidle" });
    const bare = await rowFor(page, NOTHING_RECORDED);
    ok(`${NOTHING_RECORDED} is on the register`, bare !== null);
    if (bare !== null) {
      ok(
        `${NOTHING_RECORDED}: the empty cell NAMES THE ADDRESS (DEF-CUS-6295)`,
        bare.text.includes(SENTENCE),
        JSON.stringify(bare.text),
      );
      ok(
        `${NOTHING_RECORDED}: no chip is invented for a building nobody was asked about`,
        bare.cells.flatMap((c) => c.chips).filter(Boolean).length === 0,
      );
      // B14 rule 33 — a FACT, never the rationale. No rule id, no code, no
      // sentence explaining why a master account works this way.
      ok(
        `${NOTHING_RECORDED}: and it explains nothing (B14 rule 33)`,
        !/BR-CUS|OQ-|DEF-|premises\./.test(bare.text),
        JSON.stringify(bare.text),
      );
    }

    // ── 3 · THE SAME FACT ON THE ACCOUNT'S OWN PAGE ────────────────────────
    // `GET /accounts/{id}` spreads the same row, so the header's chips come
    // from the same read. If these two ever disagree, one of them is drawing a
    // second copy of the fact — which is what this whole rule forbids.
    await page.goto(`${BASE}/${T}/accounts?q=${WITH_WATER}`, { waitUntil: "networkidle" });
    await page.click(`table tbody tr:has-text("${WITH_WATER}") a`);
    await page.waitForURL(/\/accounts\/[0-9a-f-]+/i, { timeout: 30000 });
    await page.waitForSelector(".page-header", { timeout: 20000 });
    const head = await page.$eval(".page-header", (n) => n.innerText).catch(() => "");
    // ⚠ **CASE-INSENSITIVE, AND THE FIRST DRAFT WAS NOT.** `innerText` returns
    // what is PAINTED, and the header's chip is uppercased by the kit — so the
    // header reads `WATER` and a `/Water/` test failed a perfectly correct
    // screen on both widths. A check that cannot tell a right screen from a
    // wrong one is worse than no check (hard-won law 7's third habit); the
    // sibling register walk carries the same warning about its kicker.
    ok(
      `${WITH_WATER}: the account's own page shows Water too`,
      /water/i.test(head),
      JSON.stringify(head.slice(0, 300)),
    );
    ok(
      `${WITH_WATER}: and its header does not say No services`,
      !head.includes("No services"),
      JSON.stringify(head.slice(0, 300)),
    );

    await context.close();
  }
} finally {
  if (browser) await browser.close();
  clearTimeout(KILL);
}

console.log(`\n${pass} passed, ${fail} failed`);
if (fail > 0) {
  console.log("FAILED:");
  for (const f of failures) console.log(`  · ${f}`);
  process.exit(1);
}
