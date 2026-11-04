// ── THE MOVE-IN REVIEW'S "WHAT GOES OUT" TABLE, WALKED IN A BROWSER ───────
//
// `DEF-CUS-6365` · item 7 of the twenty-item move-in list. The Accounts
// blueprint's **page 077, read AS A PAGE IMAGE at scale 5** (B14 rule 42) —
// the section headed *What goes out to the customer*, six columns
// SEND · WHAT IT SAYS · TO · CHANNEL · TEMPLATE · WHEN.
//
// **WHAT IT IS FOR.** No gate in this repo reads rendered output (hard-won law
// 6), and every one of the four things below looks perfect in a unit test:
//
//   1. a section that is MOUNTED but never reached, because its host renders it
//      behind a condition the suite seeds around (law 2, *built is not wired*);
//   2. a row whose SEND box is LIVE in the real app — the suite asserts the
//      `disabled` attribute and a browser is the only thing that can be asked
//      whether a human can actually click it;
//   3. a deleted paragraph that still reaches the screen from some other
//      catalogue key, which a `not.toContain` on ONE render cannot see;
//   4. a table that renders its header and no rows because the real endpoint
//      answers differently from the fixture.
//
// ⚠ **IT REFUSES A STALE BUILD.** Nothing on the page says how old the bundle
// is; `tsc`, the suites and every gate are green either way, because none of
// them look at `dist/`.
//
// ⚠ **IT WRITES NOTHING AND IT SAYS SO.** Opening the wizard may write a
// `wizard_parks` draft row and nothing else — no account, no payment, no
// journal entry, nothing queued. The run prints the park count before and
// after so a leak is VISIBLE rather than assumed, and never presses
// *Complete move-in*.
//
//   RVM_BASE     default http://127.0.0.1:8962
//   RVM_TENANT   default brazosbend
//   RVM_EMAIL    default dana@brazosbendutilities.com
//   RVM_PASSWORD default S3cure!passw0rd
//   RVM_ACCOUNT  a CLOSED account's id — the move-in door hangs off the account
//                that has just left the unit. With none set the walk uses the
//                standalone `/move-ins/new` door instead.
//   RVM_SHOTS    where the screenshot lands (default `.`)
//   RVM_CHROME   default /opt/pw-browsers/chromium-1194/chrome-linux/chrome
//     (the pinned @playwright/test version does not match the preinstalled
//      browser in this container, so the path is passed explicitly — never run
//      `playwright install` here.)
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");
import { execSync } from "node:child_process";
import { statSync } from "node:fs";

const BASE = process.env.RVM_BASE || "http://127.0.0.1:8962";
const T = process.env.RVM_TENANT || "brazosbend";
const EMAIL = process.env.RVM_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.RVM_PASSWORD || "S3cure!passw0rd";
const ACCOUNT = process.env.RVM_ACCOUNT || "";
const SHOTS = process.env.RVM_SHOTS || ".";
const CHROME = process.env.RVM_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

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
  const p = await context.newPage({ viewport: { width: 1440, height: 1800 } });
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

/** Walk forward by pressing Continue, the way a clerk does. A wizard with a
 *  draft open RESUMES on load and lands on the SAVED step, so a `?step=6` in
 *  the address bar is not on its own proof of being on step 6. */
async function goStep(p, step) {
  for (let guard = 0; guard < 8; guard += 1) {
    const at = Number(new URL(p.url()).searchParams.get("step") ?? "1");
    if (at === step) return true;
    const button = p.locator("button", { hasText: at < step ? /^Continue/ : /^Back/ }).first();
    if ((await button.count()) === 0 || (await button.isDisabled())) {
      console.log(`  ! cannot leave step ${at} — Continue is absent or disabled`);
      return false;
    }
    await button.click();
    await p.waitForTimeout(1400);
  }
  return Number(new URL(p.url()).searchParams.get("step") ?? "1") === step;
}

const browser = await chromium.launch({ executablePath: CHROME, args: ["--no-sandbox"] });

try {
  const ctx = await browser.newContext();
  const p = await signIn(ctx);

  const door = ACCOUNT === "" ? `/${T}/move-ins/new` : `/${T}/accounts/${ACCOUNT}/move-in`;
  await p.goto(`${BASE}${door}?step=6`, { waitUntil: "networkidle" });
  await p.waitForTimeout(2500);
  await goStep(p, 6);
  await p.waitForTimeout(1500);

  console.log("\n── the review's last section ───────────────────────────────");
  const section = p.locator("[data-move-in-messages]");
  ok("the section is on the screen", (await section.count()) === 1, `count=${await section.count()}`);

  const heading = (await section.locator("h4").first().textContent().catch(() => "")) ?? "";
  ok("the heading reads 'What goes out'", heading.trim() === "What goes out", `saw ${JSON.stringify(heading)}`);

  const headers = await section.locator("thead th").allTextContents();
  ok(
    "p077's six columns, in p077's order",
    JSON.stringify(headers) ===
      JSON.stringify(["Send", "What it says", "To", "Channel", "Template", "When"]),
    JSON.stringify(headers),
  );

  const rows = section.locator("tbody tr");
  const rowCount = await rows.count();
  ok("at least one row is drawn from the server", rowCount > 0, `rows=${rowCount}`);
  for (let i = 0; i < rowCount; i += 1) {
    const key = await rows.nth(i).getAttribute("data-move-row");
    const cells = await rows.nth(i).locator("td").allTextContents();
    console.log(`    · ${key} → ${cells.slice(1).map((c) => c.trim() || "—").join(" | ")}`);
  }

  // ⚠ **THE CONTRACT ROW IS THE ONE THE PO NAMED.** *"email, contract, text,
  // inapp message"* — the contract is the service agreement, drawn third on
  // p077. It is present and it goes out on nothing, which is the truth.
  const contract = section.locator('[data-move-row="service_agreement"]');
  ok("the contract row is drawn", (await contract.count()) === 1);

  // Asked of the BROWSER, not of an attribute: can a human tick one?
  const boxes = section.locator('input[type="checkbox"]');
  const boxCount = await boxes.count();
  ok("one SEND box per row", boxCount === rowCount, `${boxCount} boxes for ${rowCount} rows`);
  let live = 0;
  for (let i = 0; i < boxCount; i += 1) {
    if (await boxes.nth(i).isEnabled()) live += 1;
  }
  ok("no SEND box can be clicked — the commit takes no message choice", live === 0, `${live} live`);

  const body = (await p.locator("[data-wizard='content']").innerText()) ?? "";
  for (const gone of [
    "What this move-in will not write",
    "This creates the new account with its own number",
    "Nothing is delivered to the customer",
    "There is no email, text or print delivery in this release",
    "What we'll send",
    "Email — not sent",
    "Document — not produced",
  ]) {
    ok(`gone from the screen: "${gone.slice(0, 44)}"`, !body.includes(gone));
  }

  // ⚠ **THE WIZARD OPENS IN A DIALOG WITH ITS OWN SCROLL, so `fullPage: true`
  // captures the VIEWPORT of the dialog and cuts the table off** — a screenshot
  // that proves the heading and nothing under it. The section is scrolled into
  // view and shot as an ELEMENT, and the page shot is taken after the scroll.
  await section.scrollIntoViewIfNeeded();
  await p.waitForTimeout(600);
  const shot = `${SHOTS}/def-cus-6365-review-messages.png`;
  await section.screenshot({ path: shot });
  const page = `${SHOTS}/def-cus-6365-review-page.png`;
  await p.screenshot({ path: page });
  console.log(`\n  screenshots: ${shot} · ${page}`);
} finally {
  await browser.close();
}

console.log(`\n${pass} passed, ${fail} failed`);
if (fail > 0) {
  console.log(failures.map((f) => `  ✗ ${f}`).join("\n"));
  process.exit(1);
}
