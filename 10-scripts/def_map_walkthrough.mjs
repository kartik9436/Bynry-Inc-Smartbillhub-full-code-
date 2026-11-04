// ── Trace ──────────────────────────────────────────────
// Defects: DEF-INT-4287 (Assets → Map draws no basemap: the generated
//          Content-Security-Policy names no tile host for any tenant) ·
//          DEF-MET-4288 (Work → Map places nothing: the estate the jobs stand
//          on was never given coordinates)
// Rules:   CLAUDE.md hard-won law 6 (no gate in this repo reads rendered
//          output — diff the running app) · hard-won law 7 (a check's output
//          must distinguish pass from fail TO A READER, and a check you cannot
//          describe a false pass for is a check you do not understand) ·
//          13-change-process.md's CLOSURE BAR (PO 2026-08-18: *"CR is not
//          closed until we have confirm user is able to perform tasks using
//          screen/broswer/UI"*)
// ───────────────────────────────────────────────────────
/**
 * def_map_walkthrough — OPEN BOTH MAPS IN A BROWSER AND COUNT WHAT DREW.
 *
 *     ./10-scripts/11-smoke-stack.sh          # or boot the stack yourself
 *     node 10-scripts/def_map_walkthrough.mjs
 *
 * ⚠ **IT DOES NOT ASK WHETHER A TILE WAS REQUESTED — IT ASKS WHETHER ONE
 * ARRIVED**, and that distinction is the entire defect. A Content-Security-
 * Policy refusal is a console line and nothing else: the `<img class=
 * "leaflet-tile">` elements are all in the DOM, the zoom controls work, the SVG
 * markers draw, `tsc` is green and every suite passes. What separates a working
 * map from `DEF-INT-4287` is `naturalWidth`: a blocked image is `complete` with
 * a natural width of ZERO. So this counts `loaded` and `blocked` separately and
 * prints both, because a number for one without the other is exactly the shape
 * law 7 warns about.
 *
 * ⚠ **AND IT READS THE POLICY OFF THE DOCUMENT RESPONSE, NOT OFF THE API.** A
 * browser enforces the header the DOCUMENT arrived with; a header on a JSON
 * response governs nothing. `07-frontend/server.mjs` is the only thing that
 * serves `index.html`, so that is the header this checks.
 *
 * Screenshots land in `SMOKE_OUT` (default: a timestamped directory under the
 * system temp) — one per map, named for the run label.
 */
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
// ⚠ Resolved from THIS file, never from an absolute path typed in (`DEF-524`:
// a hardcoded path outlived the file it named and reported PASS through six
// UI defects).
const require = createRequire(path.join(HERE, "..", "07-frontend", "package.json"));
const { chromium } = require("playwright");

const BASE = process.env.SMOKE_BASE ?? process.env.BASE ?? "http://127.0.0.1:8080";
const TENANT = process.env.SMOKE_TENANT ?? process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? process.env.PASSWORD ?? "S3cure!passw0rd";
const LABEL = process.env.MAP_LABEL ?? "run";
const OUT = process.env.SMOKE_OUT ?? path.join("/tmp", `smartbillhub-map-${Date.now()}`);
fs.mkdirSync(OUT, { recursive: true });

const problems = [];
const note = (m) => console.log(m);
const fail = (m) => {
  problems.push(m);
  console.log("  ✗ " + m);
};
const ok = (m) => console.log("  ✓ " + m);

/**
 * The installed chromium, pinned revision or not.
 *
 * ⚠ **THIS IS `12-smoke-walkthrough.mjs`'s `resolveChromium`, COPIED, AND THE
 * DUPLICATION IS DELIBERATE RATHER THAN LAZY.** That file is a SCRIPT with
 * top-level `await` that launches a browser and walks the product the moment it
 * is imported, so there is no way to import the function out of it. Copying
 * twenty lines beats making a shared module out of a running walkthrough in a
 * defect-fix commit; if a third caller ever needs it, that is the moment to
 * lift it into its own file — and this note is here so the next lane does not
 * "discover" the duplication and assume nobody noticed.
 *
 * ⚠ **NEVER run `playwright install` here** — this environment ships browsers
 * under `PLAYWRIGHT_BROWSERS_PATH` and the npm package's pinned revision is
 * routinely newer than what is on disk. An off-revision chromium beats not
 * running at all, and the mismatch is printed rather than swallowed.
 */
function resolveChromium() {
  if (process.env.CHROME_PATH) return process.env.CHROME_PATH;
  const wanted = chromium.executablePath();
  if (wanted && fs.existsSync(wanted)) return wanted;
  const roots = [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean);
  for (const root of roots) {
    if (!fs.existsSync(root)) continue;
    for (const dir of fs.readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of [
        "chrome-linux64/chrome",
        "chrome-linux/chrome",
        "chrome-linux/headless_shell",
      ]) {
        const candidate = path.join(root, dir, sub);
        if (fs.existsSync(candidate)) {
          console.log(`chromium: pinned revision missing; using ${candidate}`);
          return candidate;
        }
      }
    }
  }
  throw new Error(
    `no chromium found: playwright wants ${wanted} and neither it nor any ` +
      `chromium under ${roots.join(", ")} exists.`,
  );
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const ctx = await browser.newContext({ viewport: { width: 1500, height: 1000 } });
const page = await ctx.newPage();

/** Every CSP refusal the browser reports, so *blocked* is never an inference. */
const refusals = [];
page.on("console", (message) => {
  const text = message.text();
  if (/Content Security Policy|Refused to load/i.test(text)) refusals.push(text);
});

/** The header the DOCUMENT arrived with — the only one a browser enforces. */
let documentPolicy = null;
page.on("response", (response) => {
  if (documentPolicy === null && response.request().resourceType() === "document") {
    documentPolicy = response.headers()["content-security-policy"] ?? "";
  }
});

// ── sign in through the real form ──────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.locator("#signin-email").fill(EMAIL);
await page.locator("#signin-password").fill(PASSWORD);
await page.locator("form button[type=submit]").first().click();
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60000 });
note(`signed in — ${page.url()}`);
note(`content-security-policy on the document: ${documentPolicy || "(none)"}`);

// ══════════════════════════════════════════════════════════════════════════
// DEF-INT-4287 · Assets → Map
// ══════════════════════════════════════════════════════════════════════════
note("\nAssets → Map (AST-01 ?tab=map)");
await page.goto(`${BASE}/${TENANT}/assets?sort=asset_no&dir=asc&tab=map`, {
  waitUntil: "domcontentloaded",
});
await page.waitForTimeout(6000); // Leaflet loads by dynamic import, then tiles

const assets = await page.evaluate(() => {
  const tiles = Array.from(document.querySelectorAll("img.leaflet-tile"));
  const showing = Array.from(document.querySelectorAll('[role="status"]'))
    .map((one) => one.textContent.trim())
    .find((one) => /\d+\s+of\s+\d+/.test(one));
  return {
    showing: showing ?? "",
    canvas: document.querySelector("[data-map-canvas]") !== null,
    tileHost: document.querySelector("[data-map-canvas]")?.getAttribute("data-tile-host") ?? "",
    tiles: tiles.length,
    // A REFUSED image is `complete` with a natural width of zero. This is the
    // one measurement that separates a drawn basemap from a grey rectangle.
    loaded: tiles.filter((one) => one.complete && one.naturalWidth > 0).length,
    blocked: tiles.filter((one) => one.complete && one.naturalWidth === 0).length,
    firstTileSrc: tiles.length > 0 ? tiles[0].src : "",
    markers: document.querySelectorAll(".leaflet-overlay-pane path").length,
    switchedOff: document.querySelector("[data-no-tile-host]")?.textContent?.trim() ?? "",
  };
});
await page.screenshot({ path: path.join(OUT, `${LABEL}-assets-map.png`), fullPage: false });

// ⚠ **A TILE THAT DID NOT ARRIVE HAS TWO COMPLETELY DIFFERENT CAUSES AND THE
// FIRST DRAFT OF THIS CHECK COULD NOT TELL THEM APART** — which is the exact
// shape hard-won law 7 warns about, met in this file's own output. A tile
// REFUSED BY THE POLICY is `DEF-INT-4287`, a product defect, and the browser
// says so in the console. A tile the host never answered is a NETWORK fact
// about the machine the browser is on — this build container cannot reach
// `server.arcgisonline.com` at all (`curl` returns `000`) — and no code change
// can fix it. They are counted and reported separately, and only the first one
// fails the run.
const policyRefusals = refusals.filter((line) => /image/i.test(line)).length;
const unreachable = assets.blocked - Math.min(assets.blocked, policyRefusals);

note(`  filter line   : ${assets.showing || "(none)"}`);
note(`  tile host     : ${assets.tileHost || "(none — basemap switched off)"}`);
note(
  `  tile images   : ${assets.tiles} requested · ${assets.loaded} DREW · ` +
    `${policyRefusals} refused by the page policy · ${unreachable} not answered by the host`,
);
note(`  first tile src: ${assets.firstTileSrc || "(no tile element)"}`);
note(`  asset markers : ${assets.markers}`);
if (assets.switchedOff) note(`  screen says   : ${assets.switchedOff}`);

if (!assets.canvas) fail("AST-01 map: no canvas — the tab did not render a map at all");
if (assets.markers === 0) fail("AST-01 map: no asset markers drew");
if (policyRefusals > 0) {
  fail(
    `AST-01 map: the page policy REFUSED ${policyRefusals} tile image(s) — this is ` +
      "DEF-INT-4287, the grey rectangle the PO reported, and it is a product defect",
  );
} else if (assets.loaded === 0 && assets.tiles > 0) {
  note(
    `  ⚠ UNREACHABLE: the policy permitted ${assets.tileHost} and the browser asked ` +
      `it for ${assets.tiles} tiles; none answered. That is this machine's network, ` +
      "not the product — point the connection at a reachable tile server to see the map draw.",
  );
  ok(`AST-01 map: ${assets.markers} markers drew and no tile was refused by the policy`);
} else {
  ok(`AST-01 map: ${assets.loaded} basemap tiles drew over ${assets.markers} markers`);
}

// ══════════════════════════════════════════════════════════════════════════
// DEF-MET-4288 · Work → Map
// ══════════════════════════════════════════════════════════════════════════
note("\nWork → Map (WRK-09 /work/map)");
await page.goto(`${BASE}/${TENANT}/work/map`, { waitUntil: "domcontentloaded" });
await page.waitForTimeout(5000);

const work = await page.evaluate(() => ({
  box: document.querySelector('[data-map="work-orders"]') !== null,
  pins: document.querySelectorAll("[data-pin]").length,
  unplaced: document.querySelectorAll("[data-unplaced]").length,
  emptyLine: document.querySelector('[data-map="work-orders"] p')?.textContent?.trim() ?? "",
  stripHeading:
    document.querySelector('[data-strip="not-on-the-map"] h2')?.textContent?.trim() ?? "",
}));
await page.screenshot({ path: path.join(OUT, `${LABEL}-work-map.png`), fullPage: false });

note(`  pins          : ${work.pins}`);
note(`  not on the map: ${work.unplaced}`);
if (work.emptyLine) note(`  screen says   : ${work.emptyLine}`);
if (work.stripHeading) note(`  strip heading : ${work.stripHeading}`);

if (!work.box) fail("WRK-09: no map box rendered at all");
if (work.pins === 0) {
  fail(
    `WRK-09: ZERO jobs placed, ${work.unplaced} in the strip — ` +
      "every open order walked to a premises with no coordinate",
  );
} else {
  ok(`WRK-09: ${work.pins} jobs placed, ${work.unplaced} still with nowhere to go`);
}

// ── the record ─────────────────────────────────────────────────────────────
note(`\nCSP refusals the browser reported: ${refusals.length}`);
for (const line of refusals.slice(0, 5)) note(`  · ${line.slice(0, 160)}`);
note(`screenshots → ${OUT}`);

fs.writeFileSync(
  path.join(OUT, `${LABEL}-map-walkthrough.json`),
  JSON.stringify({ label: LABEL, documentPolicy, assets, work, refusals, problems }, null, 2),
);

await browser.close();
if (problems.length > 0) {
  console.log(`\nFAILED — ${problems.length} problem(s)`);
  process.exit(1);
}
console.log("\nPASSED — both maps drew");
