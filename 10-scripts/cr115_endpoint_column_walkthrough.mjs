/**
 * ── Trace ──────────────────────────────────────────────
 * Change:  CR-115-BRC05 §6 lane 1 — one function decides an operation's
 *          address, and BOTH connector screens read what it returned.
 * Screens: S142 the connection view (`/:tenant/settings/integrations/:key`) ·
 *          S147 the connector set-up screen
 *          (`/:tenant/settings/connectors/:providerKey/configure`)
 * Rules:   CLAUDE.md hard-won law 6 (no gate in this repo reads rendered
 *          output — nine defects were found this way and by nothing else) ·
 *          law 7 (a check's output must tell pass from fail to a READER, and
 *          must declare what it SKIPPED beside what it checked) ·
 *          CR-115-BRC05 §3 risk 2 (the endpoint column) · B14 rule 37 (a
 *          figure drawn in a wireframe is an illustration).
 * Defects: DEF-INT-5613 is what this walk exists to SHOW FIXED — S147
 *          re-derived the address in TypeScript from one rung of a three-rung
 *          ladder and printed a dash on 9 of 91 operations where S142 printed
 *          an address. Step 3 is that comparison, on screen.
 *          DEF-INT-4259 is what step 2 exists to show STILL HOLDING — a
 *          connector with two address fields must not guess between them.
 * ───────────────────────────────────────────────────────
 *
 * RUN IT (the smoke stack's shape — the vite DEV server has no /api proxy):
 *
 *     DATABASE_URL="postgres://…/sbh_lane1?sslmode=disable" \
 *     DJANGO_SETTINGS_MODULE=config.settings.local \
 *     PYTHON="$PWD/06-backend/.venv/bin/python" \
 *     SMOKE_API_PORT=8001 SMOKE_WEB_PORT=8081 SMOKE_SKIP_SEED=1 \
 *       ./10-scripts/11-smoke-stack.sh
 *     BASE=http://127.0.0.1:8081 node 10-scripts/cr115_endpoint_column_walkthrough.mjs
 *
 * ⚠ **STEP 0 PRINTS THE BUNDLE AND THE BACKEND IT DROVE.** *Which build am I
 * looking at* is the question this CR has already got wrong twice, and a
 * browser proof that cannot name what it drove proves nothing.
 *
 * ── WHAT WOULD MAKE EACH STEP PASS WRONGLY (law 7, habit 2) ────────────────
 *  2 **A SCREEN AGREEING WITH ITSELF.** Reading the ENDPOINT cell and then
 *    reading the same value out of the same React state would pass on any
 *    resolver, right or wrong. So every cell is compared against the value
 *    `GET /api/integrations` put ON THE WIRE, fetched separately through the
 *    page's own session, and the wire value is printed beside the rendered one.
 *  3 **BOTH SCREENS DRAWING NOTHING.** Two dashes agree perfectly. So the run
 *    FAILS unless a stated number of cells carry a real address, and the
 *    number is printed — an agreement over an empty column is `DEF-INT-5502`
 *    coming back, which is the defect this whole ladder exists for.
 *  4 **MATCHING AN ENDPOINT THAT IS NOT THE ENDPOINT.** The cell is addressed
 *    by `[data-endpoint]` inside the row for a NAMED operation, never by
 *    "the monospace text on the page" — S142 draws a trace id in monospace too.
 *  5 **A DASH READ AS AN ABSENCE.** A missing element and an element holding
 *    "" are different facts, and the product's own rule is that no placeholder
 *    is drawn. So an absent cell is reported as `(no endpoint drawn)` and an
 *    empty one as `('')`, and the two are never folded together.
 *
 * ── WHAT THIS WALK DOES NOT COVER, WITH ITS NUMBER (law 7, G32's shape) ────
 * It reads what two SCREENS show. **It does not follow the call.** Three
 * registered adapters dial a compiled-in constant and ignore the configured
 * address entirely on 18 of 91 operations — `DEF-INT-5612` — and nothing here
 * would notice. Run `10-scripts/cr115_one_address_enumeration.py --adapters`
 * for that table.
 */

import { createRequire } from "node:module";
import { existsSync, readdirSync } from "node:fs";
import { join } from "node:path";

const require = createRequire("file:///home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8081";
const T = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";

//: The three cases CR-115-BRC05 §6 names, and why each one is here.
const CASES = [
  ["gis_esri", "two address fields, and ONE operation on the second (map_tiles names tile_url)"],
  ["email_smtp", "a `host` that is NOT a URL and must stay that way"],
  ["erp_aclarian", "an ERP: four doors WE publish, so the address comes from served_path"],
];

function chrome() {
  const want = chromium.executablePath();
  if (want && existsSync(want)) return want;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const d of readdirSync(root)) {
      const c = join(root, d, "chrome-linux", "chrome");
      if (existsSync(c)) return c;
    }
  }
  throw new Error("no chromium — set PLAYWRIGHT_BROWSERS_PATH (never run `playwright install`)");
}

let fails = 0;
const say = (label, ok, detail = "") => {
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${label}${detail ? " — " + detail : ""}`);
  if (!ok) fails++;
};

/** Every `[data-operation]` row's drawn endpoint, keyed by operation name.
 *
 * Three answers, never folded together, and the folding is what cost this
 * script an hour on 2026-09-17:
 *   `NO_ROW`    the operation is not on this screen at all
 *   `undefined` the row is there and draws no endpoint — which is CORRECT when
 *               nothing named one, because the product draws no placeholder
 *   `""`        a cell holding nothing, which is a different fault
 *
 * ⚠ **A WALK THAT REPORTS "no endpoint drawn" FOR A ROW IT NEVER FOUND IS
 * LOOKING AT THE WRONG THING** (hard-won law 7). S147's cell carried no
 * `data-endpoint` hook while S142's did, so the first run of this script
 * reported six FAILs against a screen that was rendering correctly. The hook
 * was added; this distinction is what would have SAID SO instead of blaming
 * the resolver.
 */
const NO_ROW = Symbol("row not on screen");

async function drawnEndpoints(page) {
  // ⚠ S147 truncates its API list until *more* is pressed. A row hidden behind
  // that button is not a row that draws no endpoint.
  const more = page.locator("[data-show-all], button:has-text('more')").first();
  if (await more.count()) {
    try {
      await more.click({ timeout: 2000 });
    } catch {
      /* not expandable on this screen — the rows are all drawn */
    }
  }
  const raw = await page.evaluate(() => {
    const out = {};
    for (const row of document.querySelectorAll("[data-operation]")) {
      const name = row.getAttribute("data-operation");
      if (!name) continue;
      const cell = row.querySelector("[data-endpoint]");
      out[name] = cell === null ? null : (cell.textContent || "").trim();
    }
    return out;
  });
  const out = {};
  for (const [name, value] of Object.entries(raw)) out[name] = value === null ? undefined : value;
  return { rows: new Set(Object.keys(raw)), endpoints: out };
}

const show = (v) =>
  v === NO_ROW ? "(ROW NOT ON SCREEN)" : v === undefined ? "(no endpoint drawn)" : v === "" ? "('')" : v;

async function main() {
  console.log("\n0 · WHAT THIS RUN IS DRIVING");
  const html = await (await fetch(`${BASE}/`)).text();
  console.log(`  SPA        ${BASE}`);
  console.log(`  bundle     ${html.match(/assets\/(index-[\w-]+\.js)/)?.[1] ?? "(none found)"}`);

  const browser = await chromium.launch({ executablePath: chrome(), args: ["--no-sandbox"] });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1800 } });
  try {
    await page.goto(`${BASE}/${T}/signin`, { waitUntil: "networkidle" });
    await page.fill("#signin-email", EMAIL);
    await page.fill("#signin-password", PASSWORD);
    await page.click('button[type="submit"]');
    await page.waitForURL(new RegExp(`/${T}/(?!signin)`), { timeout: 20000 });
    console.log(`  signed in  ${EMAIL} @ ${T}`);

    // ⚠ FETCHED THROUGH THE PAGE so it carries the session, and so the wire
    // value cannot come from a different backend than the screen's.
    const wire = await page.evaluate(async () => {
      const r = await fetch(`/api/${window.location.pathname.split("/")[1]}/integrations`, { credentials: "include" });
      return r.ok ? r.json() : { error: r.status };
    });
    if (wire.error) {
      say("GET /api/{tenant}/integrations answered", false, `status ${wire.error}`);
      return;
    }
    const byKey = Object.fromEntries((wire.providers || []).map((p) => [p.key, p]));
    console.log(`  backend    GET /api/{tenant}/integrations served ${Object.keys(byKey).length} connector(s)`);

    let drawnWithAnAddress = 0;

    for (const [key, why] of CASES) {
      const card = byKey[key];
      console.log(`\n· ${key} — ${why}`);
      if (!card) {
        say(`${key} is on the wire`, false, "the grid does not carry it");
        continue;
      }
      const served = Object.fromEntries(
        (card.operations || []).map((o) => [o.name, { v: o.endpoint, s: o.endpoint_source, f: o.endpoint_field }]),
      );
      console.log(
        `  connected  ${card.connection ? "yes" : "no"}` +
          (card.connection?.settings ? ` · settings ${JSON.stringify(card.connection.settings)}` : ""),
      );

      await page.goto(`${BASE}/${T}/settings/integrations/${key}`, { waitUntil: "networkidle" });
      const s142 = await drawnEndpoints(page);
      await page.goto(`${BASE}/${T}/settings/connectors/${key}/configure`, { waitUntil: "networkidle" });
      const s147 = await drawnEndpoints(page);

      for (const [name, { v, s, f }] of Object.entries(served)) {
        const want = v === null || v === undefined ? undefined : v;
        const a = s142.rows.has(name) ? s142.endpoints[name] : NO_ROW;
        const b = s147.rows.has(name) ? s147.endpoints[name] : NO_ROW;
        // A cell absent and a served `null` are THE SAME FACT: the product
        // draws no placeholder (B14 rule 37). A cell absent and a served
        // string are not.
        const agrees = (drawn) => (want === undefined ? drawn === undefined || drawn === "" : drawn === want);
        if (want !== undefined) drawnWithAnAddress++;
        say(
          `${key}.${name}`,
          agrees(a) && agrees(b),
          `wire ${show(want)} [${s}${f ? " · " + f : ""}] · S142 ${show(a)} · S147 ${show(b)}`,
        );
      }
    }

    // ⚠ FALSE PASS 3: two screens drawing nothing agree perfectly. The run is
    // only meaningful if the column actually SHOWED something.
    console.log("");
    say(
      "the column is not empty",
      drawnWithAnAddress > 0,
      `${drawnWithAnAddress} operation row(s) across the three connectors carry a real address; ` +
        "zero here would be an agreement over a blank column, which is DEF-INT-5502 returning",
    );
  } finally {
    await browser.close();
  }

  console.log(`\n${fails === 0 ? "ALL PASS" : fails + " FAIL(S)"}`);
  process.exit(fails === 0 ? 0 : 1);
}

main().catch((e) => {
  console.error(e);
  process.exit(2);
});
