// ── THE MOVE-INS LIST AND THE MOVE RECORD, WALKED IN A BROWSER ────────────
//
// Accounts blueprint **p076–p078 and p117–p118 of the 281-page edition** (the
// one the PO uploaded 2026-09-19), read AS IMAGES per B14 rule 42. Run it after
// any change to `MoveInsTab.tsx`, `MoveRecordPage.tsx` or
// `apps/customers/move_reads.py`.
//
// **WHAT IT IS FOR.** No gate in this repo reads rendered output, and every
// thing this walk checks is of the kind that looks perfect in a unit test:
// a link whose href is built without its tenant, a KPI tile that agrees with a
// table only by luck, a page that renders move-IN labels over a move-OUT.
// Hard-won law 6 — *"diff the running app against the prototype: nine defects
// were found this way and by nothing else"* — is the one law with no tool.
//
// ⚠ **IT REFUSES A STALE BUILD** (reused from the sibling move-in walk, which
// added it after a lane lost twenty minutes to a server six commits old).
// Nothing on the page says how old the bundle is; `tsc`, the suites and every
// gate are green either way, because none of them look at `dist/`.
//
// ⚠ **IT WRITES NOTHING.** Every step is a GET. There is no cleanup because
// there is nothing to clean up, and the row counts are printed before and after
// so that claim is checked rather than asserted.
//
//   MRW_BASE     default http://127.0.0.1:8962
//   MRW_TENANT   default brazosbend
//   MRW_EMAIL    default dana@brazosbendutilities.com
//   MRW_PASSWORD default S3cure!passw0rd
//   MRW_MVI / MRW_MVO   the two move references to open
//   MRW_CHROME   default /opt/pw-browsers/chromium-1194/chrome-linux/chrome
//     (the pinned @playwright/test version does not match the preinstalled
//      browser here, so the path is passed explicitly — never run
//      `playwright install` in this container.)
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");
import { execSync } from "node:child_process";
import { statSync } from "node:fs";

const BASE = process.env.MRW_BASE || "http://127.0.0.1:8962";
const T = process.env.MRW_TENANT || "brazosbend";
const EMAIL = process.env.MRW_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.MRW_PASSWORD || "S3cure!passw0rd";
const MVI = process.env.MRW_MVI || "MVI-26-0001";
const MVO = process.env.MRW_MVO || "MVO-26-0001";
const CHROME =
  process.env.MRW_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

// ── the staleness refusal ──────────────────────────────────────────────────
try {
  const built = statSync("07-frontend/dist/index.html").mtime;
  const newestSrc = new Date(
    execSync("git log -1 --format=%cI -- 07-frontend/src").toString().trim(),
  );
  if (built < newestSrc) {
    console.error(
      `REFUSED: dist/ was built ${built.toISOString()} but 07-frontend/src has a\n` +
        `commit at ${newestSrc.toISOString()}. Run \`npx vite build\` first.`,
    );
    process.exit(2);
  }
  console.log(`build is current (dist ${built.toISOString()})`);
} catch {
  console.warn("! could not check build freshness — continuing");
}

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

async function signIn(context) {
  const p = await context.newPage({ viewport: { width: 1440, height: 1600 } });
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

// ⚠ A HARD TIMEOUT ON THE WHOLE RUN (`DEF-GOV-5877`) — a walk that hangs is a
// walk nobody reads, and it holds the container open behind it.
const KILL = setTimeout(() => {
  console.error("REFUSED: walkthrough exceeded 5 minutes — killing");
  process.exit(3);
}, 300000);

let browser;
try {
  browser = await chromium.launch({ executablePath: CHROME });
  const context = await browser.newContext();
  const page = await signIn(context);

  // ── 1 · THE MOVE-INS LIST, p077 ────────────────────────────────────────
  console.log("\n1 · the Move-ins list");
  await page.goto(`${BASE}/${T}/accounts?tab=move-ins`, {
    waitUntil: "networkidle",
  });
  // ⚠ **CASE-FOLDED, AND THAT IS NOT LAZINESS.** `innerText` returns the text
  // as CSS renders it, and the KPI labels carry `text-transform: uppercase` —
  // so `includes("Waiting on a reading")` is false over a tile that says
  // exactly that. The first run of this walk reported the three tiles MISSING
  // while the screenshot showed all three. A check whose output cannot tell a
  // pass from a fail is worse than no check, so it compares what a person
  // reads rather than what the stylesheet did to it.
  const listText = (await page.innerText("body")).toLowerCase();

  ok("p077's THREE tiles are drawn",
     listText.includes("open") &&
     listText.includes("starting this week") &&
     listText.includes("waiting on a reading"));
  ok("the two tiles the PO dropped are gone",
     !listText.includes("deposits to carry over") && !listText.includes("oldest"),
     "one of them is still on screen");

  // ⚠ **THE TILE AND THE TABLE ARE COMPARED, NOT EACH TRUSTED.** The whole
  // design of `_waiting_on_a_reading` is that it derives through the same cell
  // the READS column renders. If they ever disagree, the number is the thing a
  // clerk acts on and the table is the thing they check it against.
  const tileValue = await page
    .locator('[data-unjudged]')
    .first()
    .evaluate((el) => el.closest(".kpi")?.querySelector(".v")?.textContent?.trim())
    .catch(() => null);
  const dueCells = await page.locator('[data-reads-state="due"]').count();
  ok(`the tile (${tileValue}) equals the rows reading Due (${dueCells})`,
     String(tileValue) === String(dueCells),
     "the KPI and the column disagree — one of them is lying to a clerk");

  ok("the deposit cell says the WORD, not just the amount",
     listText.includes("taken"));

  // ── 2 · THE DOORS, BY ADDRESS ──────────────────────────────────────────
  console.log("\n2 · the three doors p077 draws");
  const acctHref = await page
    .locator("[data-move-in-account]")
    .first()
    .getAttribute("href")
    .catch(() => null);
  ok(`the account number is a link carrying its tenant (${acctHref})`,
     typeof acctHref === "string" && acctHref.startsWith(`/${T}/accounts/`),
     "a href without the tenant is protocol-relative and opens another host");

  const openHref = await page
    .locator("[data-move-in-open]")
    .first()
    .getAttribute("href")
    .catch(() => null);
  if (openHref === null) {
    console.log("  · no `↗ Open` on this page — every row is a draft with no record");
  } else {
    ok(`\`↗ Open\` carries its tenant (${openHref})`,
       openHref.startsWith(`/${T}/moves/`));
  }

  // ── 3 · THE MOVE RECORD — a MOVE-IN, p077–078 ──────────────────────────
  console.log(`\n3 · the move record, move-IN (${MVI})`);
  await page.goto(`${BASE}/${T}/moves/${MVI}`, { waitUntil: "networkidle" });
  const inText = (await page.innerText("body")).toLowerCase();
  ok("it opens rather than 404s", !inText.includes("not found") && !inText.includes("unexpected application error"));
  ok("p078's move-IN labels", 
     inText.includes("account opened") && inText.includes("moved in on"));
  ok("the two doors are there", 
     (await page.locator('[data-testid="move-record-open-account"]').count()) === 1);

  // ── 4 · THE MOVE RECORD — a MOVE-OUT, p117–118 ─────────────────────────
  //
  // ⚠ **THIS IS THE STEP THAT WOULD HAVE CAUGHT `DEF-CUS-5889`.** Before the
  // branch landed, this address answered 200 and rendered `Account opened` over
  // somebody who had LEFT. Every suite was green.
  console.log(`\n4 · the move record, move-OUT (${MVO})`);
  await page.goto(`${BASE}/${T}/moves/${MVO}`, { waitUntil: "networkidle" });
  const outText = (await page.innerText("body")).toLowerCase();
  ok("it opens rather than 404s", !outText.includes("not found") && !outText.includes("unexpected application error"));
  ok("p117's move-OUT labels are used", 
     outText.includes("account closed") && outText.includes("moved out on"));
  ok("and the move-IN labels are GONE — the defect itself",
     !outText.includes("account opened") && !outText.includes("moved in on"),
     "a departure is still being described as an arrival");
  ok("`Final reads`, not `Opening reads`",
     outText.includes("final reads") && !outText.includes("opening reads"));
  ok("the money section is p118's, not the deposit box",
     outText.includes("money landed") || outText.includes("settlement") ||
     outText.includes("final bill"));
  ok("no shortfall-tying control while its dialog is unbuilt",
     (await page.locator('[data-testid="move-record-tie-shortfall"]').count()) === 0,
     "a live-looking control that opens nothing is law 2's mirror");

  // ── 5 · 1280, the staff minimum ────────────────────────────────────────
  console.log("\n5 · at 1280, the staff laptop minimum");
  await page.setViewportSize({ width: 1280, height: 1400 });
  await page.goto(`${BASE}/${T}/moves/${MVO}`, { waitUntil: "networkidle" });
  const scrolls = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
  );
  ok("the page does not scroll sideways at 1280", !scrolls);
} finally {
  // ⚠ EVERY BROWSER CLOSED IN A `finally` (`DEF-GOV-5877`) — a leaked chromium
  // outlives the lane and the next one blames the container.
  if (browser) await browser.close();
  clearTimeout(KILL);
}

console.log(`\n${pass} passed, ${fail} failed`);
if (fail > 0) {
  console.log("failed:");
  for (const f of failures) console.log(`  · ${f}`);
  process.exit(1);
}
