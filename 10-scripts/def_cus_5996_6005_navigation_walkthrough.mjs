// ── THE TWO NAVIGATION DEFECTS, WALKED IN A BROWSER ───────────────────────
//
// `DEF-CUS-6005` — the REQUEST # cell opens the request, on BOTH mounts.
// `DEF-CUS-5996` — a move-OUT record's `←` goes to Move-outs, a move-IN's to
//                  Move-ins.
//
// **WHY A BROWSER.** Both defects are of the kind that looks perfect in a unit
// test and fails in front of a clerk: a cell that renders the right characters
// and is not a link, and a destination that is a valid string pointing at the
// wrong tab. No gate in this repo reads rendered output; hard-won law 6 is the
// one law with no tool.
//
// ⚠ **IT CLICKS RATHER THAN READING `href`.** The DOM suites already assert the
// addresses. What they cannot see is whether the element is REACHABLE — whether
// something overlays it, whether the router answers, whether the tab that opens
// is the tab the address named. So every assertion here is made AFTER a real
// click, against `page.url()` and the page that came back.
//
// ⚠ **IT WRITES NOTHING.** Every step is a GET.
//
//   NAV_BASE     default http://127.0.0.1:8971
//   NAV_TENANT   default brazosbend
//   NAV_EMAIL / NAV_PASSWORD
//   NAV_MVI / NAV_MVO   the two move references to open
//   NAV_CHROME   default /opt/pw-browsers/chromium-1194/chrome-linux/chrome
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.NAV_BASE || "http://127.0.0.1:8971";
const T = process.env.NAV_TENANT || "brazosbend";
const EMAIL = process.env.NAV_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.NAV_PASSWORD || "S3cure!passw0rd";
const MVI = process.env.NAV_MVI || "MVI-26-0001";
const MVO = process.env.NAV_MVO || "MVO-26-0001";
const CHROME =
  process.env.NAV_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

let pass = 0, fail = 0;
const failures = [];
function ok(what, cond, detail = "") {
  if (cond) { pass += 1; console.log(`  ✓ ${what}`); }
  else { fail += 1; failures.push(what); console.log(`  ✗ ${what}${detail ? ` — ${detail}` : ""}`); }
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

const KILL = setTimeout(() => {
  console.error("REFUSED: walkthrough exceeded 5 minutes — killing");
  process.exit(3);
}, 300000);

let browser;
try {
  browser = await chromium.launch({ executablePath: CHROME });
  const context = await browser.newContext();
  const page = await signIn(context);

  // ── 1 · DEF-CUS-6005, the EMBEDDED mount — the surface the PO reported ───
  console.log("\n1 · the Requests TAB — the number is a door");
  await page.goto(`${BASE}/${T}/accounts?tab=requests`, { waitUntil: "networkidle" });

  const refLink = page.locator("a[data-request-record]").first();
  const count = await page.locator("a[data-request-record]").count();
  ok("the REQUEST # cell is a link at all", count > 0,
     "no a[data-request-record] on the tab — this is the defect");

  if (count > 0) {
    const shown = (await refLink.innerText()).trim();
    const href = await refLink.getAttribute("href");
    // ⚠ **B14 RULE 31, ASSERTED ON SHAPE AND NOT ON A FORMAT.** The first
    // draft of this walk demanded `/^SR-\d{2}-\d{4}$/` and went RED on real
    // seeded data reading `SR-CR094-01` — a perfectly good reference from a
    // CR-094 seed. The rule is *the visible value is the human reference and
    // never the id*, so that is what is checked: a reference-shaped token that
    // is NOT the uuid in the href.
    const idInHref = (href || "").split("/").pop() || "";
    ok(`the visible text is a reference (${shown})`, /^SR-[A-Za-z0-9-]+$/.test(shown), shown);
    ok("the href is tenant-scoped, not protocol-relative",
       href !== null && href.startsWith(`/${T}/requests/`), String(href));
    ok("the visible text is NOT the id in the href", shown !== idInHref, `${shown} vs ${idInHref}`);

    // THE CLICK — reachability, which no DOM test can answer
    await Promise.all([
      page.waitForURL((u) => /\/requests\/[^/]+$/.test(u.pathname), { timeout: 25000 }),
      refLink.click(),
    ]);
    const landed = new URL(page.url());
    ok("clicking the number LANDS on a request detail", /\/requests\/[^/]+$/.test(landed.pathname), landed.pathname);
    // ⚠ **WAIT FOR THE DETAIL TO SETTLE BEFORE READING IT.** `waitForURL`
    // resolves on the ROUTE change, and this page fetches its record after
    // that — so the first draft read the skeleton and reported the reference
    // missing. A check that reads the frame before the data is looking at the
    // wrong thing (law 7), and it fails in the direction that looks like a
    // product defect.
    ok("the detail opened is the one the number named",
       landed.pathname.endsWith(`/${idInHref}`), `${landed.pathname} vs ${idInHref}`);
    // ⚠ **WAIT FOR THE REFERENCE, NOT FOR THE NETWORK.** Two earlier drafts of
    // this assertion reported the reference MISSING from the detail and both
    // were wrong: `waitForURL` resolves on the ROUTE change, and
    // `networkidle` resolves before this page's record query has painted — so
    // both read a skeleton and printed a failure that looks exactly like a
    // product defect. Probed directly, the header reads
    // `REQUEST SR-CR094-01 · NOT YET CLASSIFIED`. Waiting for the TEXT is the
    // only form of this check that can tell a slow page from a wrong one (law
    // 7: a check whose output cannot distinguish pass from fail is worse than
    // none, and this one failed toward a false alarm).
    const printed = await page
      .getByText(shown, { exact: false })
      .first()
      .waitFor({ state: "visible", timeout: 20000 })
      .then(() => true)
      .catch(() => false);
    ok("and the detail prints that same reference", printed,
       "the reference never appeared on the page that opened");
  }

  // ── 2 · DEF-CUS-6005, the STANDALONE route + the eye still works ────────
  console.log("\n2 · the standalone /requests list — two doors, one destination");
  await page.goto(`${BASE}/${T}/requests`, { waitUntil: "networkidle" });
  const n2 = await page.locator("a[data-request-record]").count();
  ok("the reference is a link here too", n2 > 0);
  if (n2 > 0) {
    const first = page.locator("a[data-request-record]").first();
    const refHref = await first.getAttribute("href");
    const shown = (await first.innerText()).trim();
    // the eye, in the SAME row, must point at the SAME request
    const row = page.locator("tbody tr").filter({ has: page.locator(`a[data-request-record="${shown}"]`) }).first();
    const eye = row.locator('td:last-child a[href*="/requests/"]').first();
    const eyeHref = await eye.getAttribute("href");
    ok("the eye is still there", eyeHref !== null);
    ok("both doors open the SAME request", eyeHref === refHref, `${eyeHref} vs ${refHref}`);
  }

  // ── 3 · DEF-CUS-5996 — the move-OUT record's back control ───────────────
  console.log(`\n3 · the move-OUT record ${MVO} — where does ← go?`);
  await page.goto(`${BASE}/${T}/moves/${MVO}`, { waitUntil: "networkidle" });
  const backOut = page.locator("a.page-header-back").first();
  ok("the move-out record has a back control", (await backOut.count()) > 0);
  if ((await backOut.count()) > 0) {
    await Promise.all([
      page.waitForURL((u) => u.pathname.endsWith("/accounts"), { timeout: 25000 }),
      backOut.click(),
    ]);
    const u = new URL(page.url());
    ok("a move-OUT exits to the MOVE-OUTS tab",
       u.searchParams.get("tab") === "move-outs", `tab=${u.searchParams.get("tab")}`);
    // ⚠ **THE SELECTED TAB, NOT THE BODY TEXT — THIS ASSERTION PASSED WRONGLY
    // ON THE PRE-FIX BUILD AND THAT IS WHY IT IS WRITTEN THIS WAY.** It first
    // read `innerText("body").includes("move-outs")`, which is TRUE on the
    // Move-INS tab too, because the tab STRIP names all ten. Run against
    // 9aa89abb0 it reported ✓ beside a sibling ✗ that said `tab=move-ins` —
    // a check that cannot fail sitting next to the defect it was written for
    // (law 7). `aria-selected` is what the strip actually marks.
    const selected = (
      await page.locator('[aria-selected="true"]').first().innerText().catch(() => "")
    ).trim().toLowerCase();
    ok("and the Move-outs tab is the one SELECTED", selected.includes("move-out"), `selected: ${selected}`);
  }

  // ── 4 · the move-IN record, which must NOT have moved ───────────────────
  console.log(`\n4 · the move-IN record ${MVI} — the sibling that was already right`);
  await page.goto(`${BASE}/${T}/moves/${MVI}`, { waitUntil: "networkidle" });
  const backIn = page.locator("a.page-header-back").first();
  if ((await backIn.count()) > 0) {
    await Promise.all([
      page.waitForURL((u) => u.pathname.endsWith("/accounts"), { timeout: 25000 }),
      backIn.click(),
    ]);
    const u = new URL(page.url());
    ok("a move-IN still exits to the MOVE-INS tab",
       u.searchParams.get("tab") === "move-ins", `tab=${u.searchParams.get("tab")}`);
  }

  // ── 5 · the 404 branch, which has no `kind` to read ─────────────────────
  console.log("\n5 · a reference the tenant does not hold");
  await page.goto(`${BASE}/${T}/moves/MVO-99-9999`, { waitUntil: "networkidle" });
  const back404 = page.locator("a.page-header-back").first();
  if ((await back404.count()) > 0) {
    const href = await back404.getAttribute("href");
    ok("a 404 on an MVO- reference still exits to Move-outs",
       href !== null && href.includes("tab=move-outs"), String(href));
  }
} catch (err) {
  fail += 1;
  failures.push(`threw: ${err.message}`);
  console.error("\n!! " + err.stack);
} finally {
  if (browser) await browser.close();
  clearTimeout(KILL);
}

console.log(`\n${pass} passed · ${fail} failed`);
if (fail > 0) { console.log("failures:"); failures.forEach((f) => console.log("  · " + f)); }
process.exit(fail > 0 ? 1 : 0);
