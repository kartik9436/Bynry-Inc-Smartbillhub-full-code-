/**
 * DEF-MET-5743 walked in a browser — route setup asks for ONE page.
 *
 * HOW TO RUN IT. Django on 127.0.0.1:8601 against a seeded database, the built
 * SPA and that API behind ONE origin on 127.0.0.1:8600 (same origin, because
 * `DEFAULT_BASE_URL` is "" and every request the client makes is relative), and
 * a tenant with enough rows that a page is visibly a page — this was walked on
 * 647 premises and 136 routes. Then:
 *
 *   SBH_FRONTEND=<checkout>/07-frontend WALK_EMAIL=… WALK_PASSWORD=… \
 *   WALK_NEEDLE="Needle Terrace" node 10-scripts/def_met_5743_route_setup_paging_walkthrough.mjs
 *
 * `WALK_NEEDLE` must be a premises that sorts LAST by premise number, or
 * section D proves nothing: the whole claim is that a match the page cannot
 * contain is still found.
 *
 * WHAT WOULD MAKE THIS PASS WRONGLY: counting rows on screen. Fifty rows
 * appear whether the browser fetched fifty or nine thousand, and the old code
 * drew a correct-looking footer over a full array. So every assertion here is
 * about the REQUESTS the page made, or about a row that cannot be on page one
 * being reachable.
 */
import { createRequire } from "node:module";
import { existsSync, readdirSync, mkdirSync } from "node:fs";
import { join } from "node:path";


// Resolve `playwright` from whichever checkout is running this — never from a
// path baked in on the day it was written (DEF-524: G14's hardcoded path
// outlived the file it named and reported PASS through six UI defects).
const require = createRequire(join(process.env.SBH_FRONTEND ?? join(process.cwd(), "07-frontend"), "package.json"));
const { chromium } = require("playwright");
const BASE = "http://127.0.0.1:8600";
const T = "brazosbend";
const SHOTS = process.env.SBH_SHOTS ?? "/tmp/sbh-def5743-shots";
mkdirSync(SHOTS, { recursive: true });

function chrome() {
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean))
    if (existsSync(root)) for (const d of readdirSync(root)) {
      const c = join(root, d, "chrome-linux", "chrome"); if (existsSync(c)) return c;
    }
  throw new Error("no chromium");
}
let fails = 0;
const say = (l, ok, d = "") => (console.log(`  ${ok ? "PASS" : "FAIL"}  ${l}${d ? " — " + d : ""}`), ok || fails++);

const b = await chromium.launch({ executablePath: chrome(), args: ["--no-sandbox"] });
const p = await b.newPage({ viewport: { width: 1600, height: 1400 } });
let seen = [];
p.on("request", (r) => { if (r.url().includes("/api/")) seen.push(r.url()); });
const matching = (needle) => seen.filter((u) => u.includes(needle));
const reset = () => { seen = []; };

try {
  console.log(`DEF-MET-5743 · walking ${BASE}`);
  await p.goto(`${BASE}/${T}/signin`, { waitUntil: "networkidle" });
  await p.fill("#signin-email", process.env.WALK_EMAIL);
  await p.fill("#signin-password", process.env.WALK_PASSWORD);
  await p.click('button[type="submit"]');
  await p.waitForTimeout(3000);
  console.log("  signed in as", process.env.WALK_EMAIL, "→", p.url());

  console.log("\nA · S26 ROUTES OPS TAB — see the note in the report: `RoutesOpsPage`");
  console.log("     and `CyclesOpsPage` are MOUNTED NOWHERE (G40 says the same at the");
  console.log("     pre-fix commit), so /reads/routes redirects and this section walks");
  console.log("     the screen that IS there. The fixed components are covered by");
  console.log("     routeSetupRequests.def5743.dom.test.tsx instead.");
  reset();
  await p.goto(`${BASE}/${T}/reads/routes`, { waitUntil: "networkidle" });
  await p.waitForTimeout(2500);
  await p.screenshot({ path: `${SHOTS}/10-s26-routes.png`, fullPage: true });
  const routeCalls = matching("/routes?");
  console.log(`    /routes asked ${routeCalls.length}x: ${routeCalls.map((u) => u.split("?")[1]).join(" | ").slice(0, 200)}`);
  say(`the screen at this address is reachable`, true,
      `${routeCalls.length}: ${routeCalls.map((u) => u.split("?")[1]).join(" | ").slice(0, 200)}`);
  const footer = await p.locator(".table-pager-range").first().textContent().catch(() => "");
  console.log(`    footer: ${String(footer).trim()}`);

  console.log("\nC · SET-06 STEP 2 — THE PREMISES PICKER");
  reset();
  await p.goto(`${BASE}/${T}/settings/reference-data/routes-cycles/routes/new`, { waitUntil: "networkidle" });
  await p.waitForTimeout(2500);
  await p.fill("#rcw-route-name", "Paging walk").catch(async () => {
    const n = p.getByLabel(/Name/).first(); await n.fill("Paging walk");
  });
  await p.getByRole("button", { name: /Continue/i }).first().click();
  await p.waitForTimeout(3000);
  await p.screenshot({ path: `${SHOTS}/20-set06-step2.png`, fullPage: true });
  const picker = matching("/routes/premises-picker");
  say("ONE premises-picker request", picker.length === 1,
      `${picker.length}: ${picker.map((u) => decodeURIComponent(u.split("?")[1] ?? "")).join(" | ").slice(0, 200)}`);
  say("and it carries page + per", picker.length >= 1 && /page=1/.test(picker[0]) && /per=\d+/.test(picker[0]),
      picker[0] ?? "");

  console.log("\nC2 · PAGE 2 IS A NEW REQUEST, NOT A BROWSER SLICE");
  reset();
  const next = p.locator("button.table-page-btn").nth(1);
  if (await next.count()) {
    await next.click();
    await p.waitForTimeout(2500);
    await p.screenshot({ path: `${SHOTS}/22-set06-page2.png`, fullPage: true });
    const second = matching("/routes/premises-picker");
    say("clicking Next asks the SERVER for page 2", second.length >= 1 && second.some((u) => /page=2/.test(u)),
        second.map((u) => decodeURIComponent(u.split("?")[1] ?? "")).join(" | ").slice(0, 200));
  } else {
    say("a Next button exists on the picker", false, "no pager rendered");
  }

  console.log("\nD · A MATCH BEYOND PAGE ONE IS FOUND BY THE SERVER");
  reset();
  // ⚠ **THE TABLE'S BOX, BY ITS OWN PROMPT — NOT `input[type=search]`.** The
  // first draft took the first search-looking input on the page and got the
  // APP SHELL's global search, which answered `/search?q=` and put the needle
  // on screen in a dropdown. Both assertions then read as a pass over a picker
  // that had done nothing. That is law 7's second habit — ask what would make
  // this pass wrongly — and it is why the locator names the prompt B14 rule 19
  // requires this list to carry.
  const box = p.locator('input[placeholder*="premise #"]').first();
  console.log(`    picker search boxes: ${await box.count()}, placeholder=${await box.getAttribute("placeholder")}`);
  await box.fill(process.env.WALK_NEEDLE ?? "ZZZ");
  await p.waitForTimeout(4000);
  console.log(`    requests after typing: ${seen.join("\n      ")}`);
  await p.screenshot({ path: `${SHOTS}/21-set06-search.png`, fullPage: true });
  const searched = matching("/routes/premises-picker");
  say("typing asks the SERVER", searched.some((u) => /[?&]q=/.test(u)),
      searched.map((u) => decodeURIComponent(u.split("?")[1] ?? "")).join(" | ").slice(0, 200));
  // Read the TABLE, not the page — the global search dropdown also renders the
  // needle, and `body` innerText cannot tell the two apart.
  const tableText = await p.locator("table").first().innerText().catch(() => "");
  say(`the needle "${process.env.WALK_NEEDLE}" is IN THE TABLE although it is not on page one`,
      tableText.includes(process.env.WALK_NEEDLE ?? "ZZZ"),
      tableText.split("\n").slice(0, 3).join(" / "));

  console.log("\nE · SET-07 STEP 2 — THE ROUTE PICKER");
  reset();
  await p.goto(`${BASE}/${T}/settings/reference-data/routes-cycles/cycles/new`, { waitUntil: "networkidle" });
  await p.waitForTimeout(2500);
  const cname = p.getByLabel(/Name/).first();
  await cname.fill("Paging walk cycle");
  await p.getByRole("button", { name: /Continue/i }).first().click();
  await p.waitForTimeout(3000);
  await p.screenshot({ path: `${SHOTS}/30-set07-step2.png`, fullPage: true });
  const cyclePicker = matching("/routes?");
  say("the cycle wizard asks /routes for a PAGE", cyclePicker.length >= 1 && /page=1/.test(cyclePicker[0]),
      cyclePicker.map((u) => decodeURIComponent(u.split("?")[1] ?? "")).join(" | ").slice(0, 200));
  say("and it is not handed every route by the page above it",
      cyclePicker.every((u) => /per=\d+/.test(u) && !/per=1000/.test(u)),
      cyclePicker.map((u) => u.split("?")[1]).join(" | ").slice(0, 160));
} catch (error) {
  console.log("  WALK ERROR:", String(error).split("\n")[0]);
  await p.screenshot({ path: `${SHOTS}/99-error.png`, fullPage: true }).catch(() => undefined);
  fails++;
} finally {
  await b.close();
  console.log(fails === 0 ? "\nALL PASS" : `\n${fails} FAIL`);
  process.exit(fails === 0 ? 0 : 1);
}
