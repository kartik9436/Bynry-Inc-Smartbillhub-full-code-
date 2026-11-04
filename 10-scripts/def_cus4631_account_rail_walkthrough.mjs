// ── Trace ──────────────────────────────────────────────
// Change:   DEF-CUS-4631 — the S21 account icon rail. PO: *"in account - view we
//           have all those icons - can you activate them now"*, then *"activate
//           all of them"*.
// Rules:    BR-SHL-045 (the seven glyphs) · BR-SHL-025 (a control with no
//           endpoint is DISABLED WITH ITS REASON) · B14 rule 6 (danger tier)
//           CLAUDE.md hard-won law 6 (*"diff the running app against the
//           prototype — no gate looks at rendered output"*) and the PO's
//           standing rule: *"ensure you do web walkthorugh before you sign off"*.
// ───────────────────────────────────────────────────────
//
// WHY A BROWSER AND NOT ANOTHER UNIT TEST
// ───────────────────────────────────────
// The defect this walks was invisible to `tsc`, to 636 passing frontend cases
// and to every gate, and the PO found it by LOOKING AT THE SCREEN. Two of the
// test files that should have caught it were asserting the false sentences
// word for word. So the check that matters here is the one nothing else in the
// repo performs: open the real screen against the real API and CLICK.
//
// WHAT IT ASSERTS, on three accounts chosen for their FACTS rather than at
// random — because every refusal on this rail is now derived from a fact:
//
//   1. an OCCUPIED account WITH issued bills   → six of seven live; the ✉
//                                                statement is the only refusal
//   2. an occupied account with NO issued bill → 🖨 and $ refuse, and the
//                                                sentence is about THIS account
//   3. a CLOSED (terminal) account             → ⚡ refuses on occupancy
//
// …and then it CLICKS the three newly-released glyphs and follows where each
// one lands, because a control that opens onto a blank page is the same defect
// wearing the other face (`DEF-CWP-3925`, the portal's `//portal/…` links).
//
// ENV: RAIL_BASE · RAIL_TENANT · RAIL_EMAIL · RAIL_PASSWORD · RAIL_OUT
//      RAIL_ACC_BILLS · RAIL_ACC_NOBILL · RAIL_ACC_CLOSED (account UUIDs)
import { existsSync, mkdirSync, readdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = (process.env.RAIL_BASE ?? "http://127.0.0.1:8112").replace(/\/$/, "");
const TENANT = process.env.RAIL_TENANT ?? "brazosbend";
const EMAIL = process.env.RAIL_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.RAIL_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.RAIL_OUT ?? join(tmpdir(), "rail-walk");
const ACC_BILLS = process.env.RAIL_ACC_BILLS ?? "";
const ACC_NOBILL = process.env.RAIL_ACC_NOBILL ?? "";
const ACC_CLOSED = process.env.RAIL_ACC_CLOSED ?? "";

mkdirSync(OUT, { recursive: true });
const failures = [];
const fiveHundreds = [];
const notes = [];

function ok(msg) {
  console.log(`  ✓ ${msg}`);
}
function fail(msg) {
  failures.push(msg);
  console.error(`  ✗ ${msg}`);
}

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  const roots = [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean);
  for (const root of roots) {
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
  throw new Error(`no chromium found (looked in ${roots.join(", ")})`);
}

/** The seven glyphs as the browser sees them: name → {disabled, title}. */
async function readRail(page) {
  return page.$$eval("[data-account-icon-rail] button", (buttons) =>
    buttons.map((b) => ({
      name: b.getAttribute("aria-label") ?? "",
      title: b.getAttribute("title") ?? "",
      disabled: b.hasAttribute("disabled"),
      variant: b.getAttribute("data-variant") ?? "",
    })),
  );
}

async function openAccount(page, accountId, shot) {
  await page.goto(`${BASE}/${TENANT}/accounts/${accountId}`, { waitUntil: "networkidle" });
  await page.waitForSelector("[data-account-icon-rail]", { timeout: 20000 });
  // The bills read the rail derives from is a second request; let it settle so
  // the walk measures the ANSWER and not the "Checking…" state.
  await page.waitForTimeout(1500);
  await page.screenshot({ path: join(OUT, `${shot}.png`), fullPage: false });
  return readRail(page);
}

const browser = await chromium.launch({ executablePath: resolveChromium(), headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await context.newPage();
page.on("response", (r) => {
  if (r.status() >= 500) fiveHundreds.push(`${r.status()} ${r.request().method()} ${r.url()}`);
});

try {
  // ── sign in ──────────────────────────────────────────────────────────────
  console.log("── sign-in");
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(`**/${TENANT}/dashboard`, { timeout: 25000 });
  ok("signed in");

  // ── 1 · an OCCUPIED account WITH issued bills ────────────────────────────
  console.log("\n── account WITH issued bills (all but the statement should be live)");
  const railA = await openAccount(page, ACC_BILLS, "01-account-with-bills");
  if (railA.length !== 7) fail(`rail has ${railA.length} glyphs, expected 7`);
  for (const g of railA) console.log(`     ${g.disabled ? "✗" : "✓"} ${g.name} — "${g.title}"`);

  const byName = Object.fromEntries(railA.map((g) => [g.name, g]));
  for (const name of [
    "Print bill",
    "Issue credit",
    "Change plan",
    "Disconnect notice",
    "Payment plan",
    "Add note",
  ]) {
    const g = byName[name];
    if (!g) fail(`${name} is missing from the rail`);
    else if (g.disabled) fail(`${name} is STILL DISABLED — "${g.title}"`);
    else ok(`${name} is live`);
  }
  if (!byName["Send statement"]?.disabled) {
    fail("Send statement is enabled — nothing renders a statement, so this would open a blank page");
  } else {
    ok(`Send statement refuses, truthfully: "${byName["Send statement"].title}"`);
  }
  // B14 rule 6 — the destructive one is told apart by COLOUR, not only shape.
  if (byName["Disconnect notice"]?.variant !== "ghost-danger") {
    fail(`Disconnect notice variant is "${byName["Disconnect notice"]?.variant}", expected ghost-danger`);
  } else ok("Disconnect notice carries the danger tier (B14 rule 6)");

  // ── the PLAN TAB collision (task one) ────────────────────────────────────
  const tabs = await page.$$eval('[role="tab"]', (els) => els.map((e) => e.textContent.trim()));
  if (tabs.includes("Plan")) fail(`a bare "Plan" tab is still drawn: ${JSON.stringify(tabs)}`);
  else if (!tabs.includes("Payment plan")) fail(`no "Payment plan" tab: ${JSON.stringify(tabs)}`);
  else ok('the tab reads "Payment plan", not "Plan"');
  const headerText = await page.textContent("body");
  if (headerText.includes("Plan from unit")) {
    ok('the header still says "Plan from unit" — the RATE plan, now unambiguous');
  } else {
    notes.push('header did not show "Plan from unit" on this account (it may have no unit plan)');
  }

  // ── 2 · CLICK the three released glyphs, and see where each lands ────────
  console.log("\n── clicking 🖨 Print bill");
  await page.click('[data-account-icon-rail] button[aria-label="Print bill"]');
  await page.waitForTimeout(2500);
  let url = page.url();
  await page.screenshot({ path: join(OUT, "02-print-bill.png"), fullPage: false });
  if (!/\/billing\/bills\/[^/]+\/document/.test(url)) fail(`Print bill landed at ${url}`);
  else ok(`Print bill → ${url.replace(BASE, "")}`);
  let body = await page.textContent("body");
  if (/not built yet|Page not found|404/i.test(body)) fail("Print bill opened a not-built page");
  else ok("the bill document page rendered");

  console.log("\n── clicking $ Issue credit");
  await openAccount(page, ACC_BILLS, "03-back-to-account");
  await page.click('[data-account-icon-rail] button[aria-label="Issue credit"]');
  await page.waitForTimeout(2500);
  url = page.url();
  await page.screenshot({ path: join(OUT, "04-issue-credit.png"), fullPage: false });
  if (!/\/billing\/fix\?bill=/.test(url)) fail(`Issue credit landed at ${url}`);
  else ok(`Issue credit → ${url.replace(BASE, "")}`);
  // ⚠ ASSERTED ON THE SCREEN'S OWN HEADING, NOT ON THE ABSENCE OF THE WORDS
  // "not built yet". The first draft of this walk searched the whole body for
  // that phrase and FAILED on a perfectly healthy screen: `BIL-01.fix` carries
  // a legitimate closing note — *"Adding your own reason codes needs the
  // reference table that is not built yet"* — so the check was reading another
  // feature's honest absence as this one's failure. That is law 7's "ask what
  // would make this check report wrongly", caught by looking at the screenshot
  // instead of trusting the exit code.
  if (!(await page.$('text=Which bill, and what went wrong'))) {
    fail("Issue credit did not open the Fix-a-bill step 1");
  } else ok("the bill-correction workflow rendered (step 1: which bill, and what went wrong)");
  const billField = await page.inputValue("#bil-fix-invoice").catch(() => null);
  if (billField && /^[0-9a-f]{8}-[0-9a-f]{4}-/i.test(billField)) {
    notes.push(
      `B14 rule 31 — the Fix-a-bill "Bill" field shows the raw database id ${billField}. ` +
        "PRE-EXISTING (BillDetailPage's 'Correct this bill' link reaches the same screen the " +
        "same way) and filed rather than fixed here: it is billing's screen, not this lane's.",
    );
  }

  console.log("\n── clicking ⚡ Disconnect notice");
  await openAccount(page, ACC_BILLS, "05-back-to-account");
  await page.click('[data-account-icon-rail] button[aria-label="Disconnect notice"]');
  await page.waitForTimeout(2500);
  url = page.url();
  await page.screenshot({ path: join(OUT, "06-disconnect-notice.png"), fullPage: false });
  if (!url.includes("/disconnects/new")) fail(`Disconnect notice landed at ${url}`);
  else ok(`Disconnect notice → ${url.replace(BASE, "")}`);
  if (!url.includes(`account=${ACC_BILLS}`)) fail("the wizard did not receive the account prefill");
  else ok("the wizard opened with THIS account preselected");
  body = await page.textContent("body");
  if (/not built yet|Page not found/i.test(body)) fail("Disconnect notice opened a not-built page");
  else ok("the DSC-02 wizard rendered");

  // ── 3 · an account with NO issued bill — the derived refusal ─────────────
  console.log("\n── account with NO issued bill (the two bill-backed glyphs must refuse)");
  const railB = await openAccount(page, ACC_NOBILL, "07-account-no-bill");
  const byNameB = Object.fromEntries(railB.map((g) => [g.name, g]));
  for (const g of railB) console.log(`     ${g.disabled ? "✗" : "✓"} ${g.name} — "${g.title}"`);
  for (const [name, want] of [
    ["Print bill", "No bill has been issued yet."],
    ["Issue credit", "A credit needs an issued bill."],
  ]) {
    const g = byNameB[name];
    if (!g?.disabled) fail(`${name} is live on an account with no issued bill`);
    else if (g.title !== want) fail(`${name} says "${g.title}", expected "${want}"`);
    else ok(`${name} refuses with the derived sentence: "${g.title}"`);
  }
  if (byNameB["Disconnect notice"]?.disabled) {
    fail("Disconnect notice refused on an OCCUPIED account — it is gated on occupancy, not bills");
  } else ok("Disconnect notice is unaffected by the bill facts");

  // ── 4 · a CLOSED account — the occupancy refusal ─────────────────────────
  console.log("\n── CLOSED account (⚡ must refuse on occupancy)");
  const railC = await openAccount(page, ACC_CLOSED, "08-account-closed");
  const byNameC = Object.fromEntries(railC.map((g) => [g.name, g]));
  for (const g of railC) console.log(`     ${g.disabled ? "✗" : "✓"} ${g.name} — "${g.title}"`);
  const cut = byNameC["Disconnect notice"];
  if (!cut?.disabled) fail("Disconnect notice is live on a closed account");
  else if (cut.title !== "This account does not hold service.")
    fail(`Disconnect notice says "${cut.title}"`);
  else ok(`Disconnect notice refuses: "${cut.title}"`);
  if (byNameC["Print bill"]?.disabled)
    notes.push(`Print bill on the closed account: "${byNameC["Print bill"].title}"`);
  else ok("Print bill stays live on a closed account — a final bill is still reprintable");
} catch (error) {
  fail(`walkthrough threw: ${error.message}`);
  await page.screenshot({ path: join(OUT, "99-threw.png") }).catch(() => {});
} finally {
  await browser.close();
}

if (fiveHundreds.length) for (const line of fiveHundreds) fail(`5xx: ${line}`);
writeFileSync(join(OUT, "result.txt"), [...failures, ...notes].join("\n"));
console.log(`\nscreenshots: ${OUT}`);
if (notes.length) {
  console.log("notes:");
  for (const n of notes) console.log(`  · ${n}`);
}
console.log(failures.length ? `\nFAILED (${failures.length})` : "\nALL CHECKS PASSED");
process.exit(failures.length ? 1 : 0);
