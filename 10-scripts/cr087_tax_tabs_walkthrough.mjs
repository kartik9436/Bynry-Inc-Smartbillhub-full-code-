// ── Trace ──────────────────────────────────────────────
// Change:  CR-087 — the tax detail's `Plans` and `Audit` tab bodies, its KPI
//          strip, the one writable `Remittance & filings` block, and the
//          CORRECTION door on `Edit` (PO ruling 2026-09-10: *"build"*).
// Rules:   hard-won law 6 (no gate in this repo reads rendered output) ·
//          hard-won law 2's mirror (a live screen behind a dead control) ·
//          B14 rule 31 (no database id on screen) · BR-RAT-104 · BR-RAT-113
// ───────────────────────────────────────────────────────
//
// WHAT THIS OPENS THAT `cr087b_tax_screens_walkthrough.mjs` DOES NOT, AND WHY
// EACH ONE NEEDED A BROWSER AND A LIVE SERVER.
//
//   1 · the four KPI tiles, read as TEXT. Two of them were an em-dash on every
//       tax that has ever existed and a unit test on the presenter cannot say
//       what the strip renders.
//   2 · the two tab BODIES, which did not exist. A table's HEADERS and its
//       ROWS, so a column that renders an id instead of a name (B14 rule 31)
//       is visible rather than inferred.
//   3 · the writable block's HEADINGS, counted — the defect was that nine
//       filing facts appeared TWICE, and `toContain` passes on both states.
//   4 · ⚠ **THE CORRECTION DOOR, AGAINST A LIVE SERVER, WHICH IS THE ONLY WAY
//       `DEF-RAT-4838` COULD HAVE BEEN FOUND.** The client's `taxIsInForce` is
//       a DATE test and `update_tax`'s refusal is `not tax.is_draft`; two
//       layers held two correct expressions of one rule and neither could see
//       the other. A test on either side passes. This walk PATCHes a tax the
//       client believed editable and reads the 409 the server actually sends.
//
// Prerequisites: the deployed join (see `11-smoke-stack.sh`) — a backend and
// `07-frontend/server.mjs` over a built bundle. BASE defaults to the port that
// script uses.
import { existsSync, readdirSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8401";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr087-tax-tabs";
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome", "chrome-linux/headless_shell"]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  throw new Error("no chromium found");
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const say = (...parts) => console.log(...parts);

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
say("signed in as", EMAIL);

await page.goto(`${BASE}/${TENANT}/plans-rates/taxes-fees`, { waitUntil: "networkidle" });
const href = await page.$eval("table a[href*='/taxes-fees/']", (a) => a.getAttribute("href"));
const id = href.split("/").pop();
say("first tax:", href);

// ── 1 · the strip, the sub-line and the absence bar ─────────────────────────
await page.goto(`${BASE}${href}`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
const tiles = await page.$$eval(".kpi", (ns) => ns.map((n) => n.innerText.replace(/\n+/g, " | ").trim()));
say("KPI TILES:", JSON.stringify(tiles));
// ⚠ THE ASSERTION IS THE ABSENCE OF AN EM-DASH. Two of these four read "—" on
// every tax that has ever existed — `PRB-06`, furniture rather than a stated
// absence — and the fix is only real if no tile renders one.
say("  any permanent em-dash:", tiles.some((t) => /\|\s*—\s*(\||$)/.test(t)));
// ⚠ **THE STATUS IS SHOWN ONCE — PO RULING 2026-09-10, verbatim *"show only one
// status"*.** The blueprint drew it as the pill under the title AND as tile 3,
// rendering the same `row.status` twice. Both halves are asserted, because
// removing the tile is only half the ruling: a strip with no status AND a
// header with no pill would satisfy a "not twice" check and be a worse screen.
// This lives in the WALKTHROUGH rather than only in a unit test because the
// presenter test can say what the tiles CARRY and cannot say what a person SEES.
const STATUS_WORDS = ["Active", "Draft", "Retired", "Superseded"];
// ⚠ **THE SELECTOR IS `.pill`, NOT THE HEADER'S TEXT.** The first draft of this
// check read `.page-header-rollup`, which is the SUB-LINE and never held the
// status, so it reported "no status in the header" over a page that was showing
// one — a check that fails wrongly, which is worse than no check. `StatusPill`
// renders `<span className="pill …">` and that is what a reader actually sees.
const pills = await page.$$eval(".pill", (ns) => ns.map((n) => n.textContent.trim()));
const inHeader = STATUS_WORDS.filter((w) => pills.some((x) => new RegExp(`\\b${w}\\b`).test(x)));
const inStrip = STATUS_WORDS.filter((w) => new RegExp(`\\b${w}\\b`).test(tiles.join(" | ")));
say("  STATUS in the header (must be NON-empty):", JSON.stringify(inHeader));
say("  STATUS inside the KPI strip (must be EMPTY):", JSON.stringify(inStrip));
say("SUB-LINE:", (await page.textContent(".page-header-rollup")).trim().slice(0, 260));
const bar = await page.$("[data-tax-absences]");
say("ABSENCE BAR:", bar !== null, bar ? `| closed by default: ${!(await bar.evaluate((n) => n.hasAttribute("open")))}` : "");

// ── 2 · the remittance block, ONCE ──────────────────────────────────────────
const heads = await page.$$eval("[data-tax-remittance-form] h3", (ns) => ns.map((n) => n.textContent.trim()));
say("WRITABLE BLOCK HEADINGS:", JSON.stringify(heads));
say("  'Filing details' anywhere on the page (must be false):", (await page.content()).includes("Filing details"));
say("BLOCKS:", JSON.stringify(await page.$$eval("[data-definition-block]", (ns) => ns.map((n) => n.dataset.definitionBlock))));
await page.screenshot({ path: `${OUT}/overview.png`, fullPage: true });

// ── 3 · the two tab bodies ──────────────────────────────────────────────────
for (const [tab, hook] of [["plans", "data-tax-plans"], ["audit", "data-tax-versions"]]) {
  await page.goto(`${BASE}${href}?tab=${tab}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  say(`\n== ?tab=${tab} ==`);
  const table = await page.$(`[${hook}] table`);
  if (table) {
    say("  HEADERS:", JSON.stringify(await page.$$eval(`[${hook}] thead th`, (ns) => ns.map((n) => n.textContent.trim()))));
    const rows = await page.$$eval(`[${hook}] tbody tr`, (ns) => ns.map((r) => [...r.cells].map((c) => c.innerText.trim())));
    say("  ROWS:", JSON.stringify(rows));
    // B14 rule 31 — a uuid in a cell is the one thing these tables must never
    // print, and it is invisible to a source check.
    const uuid = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;
    say("  a uuid in any cell (must be false):", rows.flat().some((c) => uuid.test(c)));
  } else {
    const panel = await page.$(`[${hook}]`);
    say("  no table; panel says:", panel ? (await panel.innerText()).replace(/\n+/g, " | ").trim() : "PANEL MISSING");
  }
  const band = await page.$("[data-accent-band]");
  if (band) say("  CALLOUT:", (await band.innerText()).replace(/\n+/g, " | ").trim());
  await page.screenshot({ path: `${OUT}/${tab}.png`, fullPage: true });
}

// ── 4 · the correction door, against the server ─────────────────────────────
say("\n== the correction door ==");
const refused = await page.evaluate(
  async ({ id, tenant }) => {
    const r = await fetch(`/api/${tenant}/taxes/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ effective_from: "2026-01-01" }),
    });
    return { status: r.status, body: (await r.text()).slice(0, 160) };
  },
  { id, tenant: TENANT },
);
// ⚠ **THIS IS `DEF-RAT-4838`'s OWN MEASUREMENT.** A 409 here over a tax the
// wizard is about to offer `Save changes` on is the two layers disagreeing.
say("PATCH a rate-history field ->", refused.status, refused.body.slice(0, 110));

await page.goto(`${BASE}/${TENANT}/plans-rates/taxes-fees/${id}/edit?step=3`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
const body = await page.innerText("body");
say("CORRECTION PANEL on screen:", body.includes("Saving writes a new dated version"));
say("OLD DEAD REFUSAL on screen (must be false):", body.includes("that route has not been built"));
say("REASON BOX:", (await page.$("#reason")) !== null);
const commits = await page.$$eval("button", (bs) =>
  bs.filter((b) => /Save/.test(b.textContent)).map((b) => ({ label: b.textContent.trim(), disabled: b.disabled })),
);
say("COMMIT BUTTONS:", JSON.stringify(commits));
const rows = await page.$$eval("dl div", (ns) => ns.map((n) => n.innerText.replace(/\n+/g, " = ").trim()).filter(Boolean));
say("REVIEW READ-BACK:", JSON.stringify(rows));
await page.screenshot({ path: `${OUT}/correction.png`, fullPage: true });

// ── 5 · 1280, the staff app's laptop minimum ────────────────────────────────
await page.setViewportSize({ width: 1280, height: 1000 });
await page.goto(`${BASE}${href}?tab=plans`, { waitUntil: "networkidle" });
await page.waitForTimeout(1000);
say(
  "\n1280 · the page body scrolls sideways (must be false):",
  await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth),
);
await page.screenshot({ path: `${OUT}/plans-1280.png`, fullPage: true });
say("screenshots:", OUT);
await browser.close();
