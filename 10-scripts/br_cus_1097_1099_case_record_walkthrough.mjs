// ── Trace ────────────────────────────────────────────────────────────────────
// Rules:   BR-CUS-1097 (PO 2026-09-25 — *"Show what's still owed and let the
//          clerk proceed"*) · BR-CUS-1099 (*"So we warn user , but we dont stop
//          user"*) · BR-CUS-1096 (their pair) · B14 rule 33 · rule 41 · rule 42
//          (the drawing is read AS AN IMAGE — blueprint p143/p144/p145)
// Defects: DEF-CUS-6735 · DEF-CUS-6736 · DEF-CUS-6755 · DEF-CUS-6756 ·
//          DEF-CUS-6757 · DEF-CUS-6758
// ─────────────────────────────────────────────────────────────────────────────
//
// ⚠ **THIS IS THE ONLY CHECK IN THE REPOSITORY THAT READS RENDERED OUTPUT, AND
// IT IS A PERSON WITH A BROWSER** (hard-won law 6). Every assertion below is one
// a unit test cannot make: it drives the shipped bundle through a real router, a
// real query client and a real API, against real disconnect cases.
//
// ⚠ **IT WRITES ONE THING AND SAYS SO.** `--hold` records a protection on the
// case it is given, which is a real row on a real account. Without that flag it
// opens both dialogs and submits neither. The cut and the reconnection are NOT
// submitted here at all — those are acts against a household's supply.
//
// ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** A mid-run reseed looks
// exactly like a broken screen.
//
//   10-scripts/proof-db.sh clone cutpath --export
//   BASE=http://127.0.0.1:8472 node 10-scripts/br_cus_1097_1099_case_record_walkthrough.mjs
//
// Environment: BASE · TENANT · EMAIL · PASSWORD · SHOTS · CHROME ·
//   CASE_SCHEDULED (ready to cut) · CASE_NO_PROOF (tier 3, no certified proof)
//   CASE_CUT (cut, still owing)
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
// `ROOT` is derived from this file's own path (`DEF-CUS-6028`): a walk that
// hard-codes `/home/user/SMARTBillHub` drives YOUR bundle and then reads the
// SHARED checkout's Django, which is on somebody else's branch.
const ROOT = path.resolve(HERE, "..");
const require = createRequire(path.join(ROOT, "07-frontend/package.json"));
const { chromium } = require("playwright");

const BASE = process.env.BASE || "http://127.0.0.1:8472";
const T = process.env.TENANT || "brazosbend";
const EMAIL = process.env.EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD || "S3cure!passw0rd";
const CHROME = process.env.CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const SHOTS = process.env.SHOTS || "/tmp/cutpath-shots";
const CASE_SCHEDULED = process.env.CASE_SCHEDULED || "dsc-26-0006";
const CASE_NO_PROOF = process.env.CASE_NO_PROOF || "dsc-26-0008";
const CASE_CUT = process.env.CASE_CUT || "dsc-26-0007";
const WRITE_HOLD = process.argv.includes("--hold");

let pass = 0;
const failures = [];
const pageErrors = [];
const ok = (what) => { pass += 1; console.log(`  ✓ ${what}`); };
const bad = (what, saw) => { failures.push(`${what} — saw: ${saw}`); console.log(`  ✗ ${what}\n      saw: ${saw}`); };
const is = (cond, what, saw) => (cond ? ok(what) : bad(what, saw));

const browser = await chromium.launch({ executablePath: CHROME });

async function signIn(width) {
  const ctx = await browser.newContext({ viewport: { width, height: 1600 } });
  const p = await ctx.newPage();
  p.setDefaultTimeout(25000);
  p.on("pageerror", (e) => pageErrors.push(`PAGEERROR ${e.message}`));
  await p.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
  await p.fill("#signin-email", EMAIL);
  await p.fill("#signin-password", PASSWORD);
  await Promise.all([
    p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
    p.click('button[type="submit"]'),
  ]);
  return p;
}

async function record(p, ref) {
  await p.goto(`${BASE}/${T}/disconnects/${ref}`, { waitUntil: "domcontentloaded" });
  await p.waitForLoadState("networkidle");
  return p;
}

for (const width of [1440, 1280]) {
  console.log(`\n════ ${width}px — the staff app's two required widths (PO 2026-09-10)`);
  const p = await signIn(width);

  // ── BR-CUS-1099 · a cut with no recorded proof is WARNED, not refused ────
  await record(p, CASE_NO_PROOF);
  const markNoProof = p.getByRole("button", { name: "Mark as cut" }).first();
  const refusedText = await p.getByTestId("disconnect-record-cut-refused").innerText().catch(() => "");
  is(
    !refusedText.includes("No proof"),
    "BR-CUS-1099 · the missing certified proof is no longer the reason the button is grey",
    refusedText || "(no refusal strip)",
  );
  const warnNoProof = await p.getByTestId("disconnect-record-warnings").innerText().catch(() => "");
  is(
    warnNoProof.includes("No proof of service recorded."),
    "BR-CUS-1099 · and it IS still said, as a warning, in six words or fewer (B14 rule 33)",
    warnNoProof || "(no warnings list)",
  );
  await p.screenshot({ path: `${SHOTS}/${width}-no-proof.png`, fullPage: true });

  // ── the cut path itself: a properly scheduled case can be recorded ───────
  await record(p, CASE_SCHEDULED);
  const markReady = p.getByRole("button", { name: "Mark as cut" }).first();
  is(await markReady.count() > 0 && !(await markReady.isDisabled()),
    "a scheduled case with its services named offers a LIVE `Mark as cut`",
    `count=${await markReady.count()} disabled=${await markReady.count() ? await markReady.isDisabled() : "n/a"}`);
  await markReady.click();
  await p.waitForTimeout(700);
  const cutDialog = await p.locator("[role=dialog]").innerText();
  is(cutDialog.includes("Services"), "p145 · the dialog STATES the services rather than choosing them", cutDialog.slice(0, 120));
  await p.screenshot({ path: `${SHOTS}/${width}-cut-dialog.png`, fullPage: true });
  await p.getByRole("button", { name: "Cancel" }).first().click();
  await p.waitForTimeout(400);

  // ── p144 · the Hold dialog ───────────────────────────────────────────────
  await p.getByRole("button", { name: "Hold the case" }).first().click();
  await p.waitForTimeout(700);
  const dialog = p.locator("[role=dialog]");
  const holdText = await dialog.innerText();

  // DEF-CUS-6757 — the fourth reason is not offered.
  is(!holdText.includes("A bill is disputed"), "DEF-CUS-6757 · the dispute reason is not offered", holdText.slice(0, 400));
  is(!holdText.includes("A dispute cannot be recorded here."), "DEF-CUS-6757 · and its refusal is gone with it", "(still present)");
  for (const reason of ["Medical certificate", "Weather moratorium", "Payment plan"]) {
    is(holdText.includes(reason), `p144 · the three real reasons are still drawn — ${reason}`, holdText.slice(0, 400));
  }

  // DEF-CUS-6755 — p144's third drawn promise is kept.
  const effects = await dialog.getByTestId("disconnect-hold-effects").innerText();
  is(effects.includes("The case moves to On hold."), "DEF-CUS-6755 · p144's `the case moves to On hold` is promised again", effects);
  is(effects.includes("The cut date stays."), "p144 · and the promise that is still NOT kept is stated as its own consequence", effects);

  // DEF-CUS-6756 / DEF-CUS-6758 — the button says what is missing.
  await dialog.getByRole("button", { name: "Hold the case" }).click();
  await p.waitForTimeout(700);
  const afterEmpty = await dialog.innerText();
  is(afterEmpty.includes("Give a review date."),
    "DEF-CUS-6756 · pressing with an empty `Review on` now SAYS what is missing",
    afterEmpty.slice(0, 500));
  await p.screenshot({ path: `${SHOTS}/${width}-hold-empty-review.png`, fullPage: true });
  await p.getByRole("button", { name: "Cancel" }).first().click();
  await p.waitForTimeout(400);

  // ── BR-CUS-1097 · a cut account that still owes money can be reconnected ─
  await record(p, CASE_CUT);
  // ⚠ **A LINK, NOT A BUTTON, SINCE S148 LANDED** — and the assertion is on the
  // ADDRESS rather than on the control being enabled, because a door that opens
  // onto the wrong screen passes every "is it clickable" check ever written
  // (hard-won law 2's mirror, and the reason `ReconnectPage.dom.test.tsx`
  // asserts the same address by screen id).
  const reconnect = p.getByTestId("disconnect-record-reconnect");
  const href = await reconnect.getAttribute("href").catch(() => null);
  is(await reconnect.count() > 0,
    "BR-CUS-1097 · Brett Calloway's case — a cut account that still owes money offers a reconnect door",
    `count=${await reconnect.count()}`);
  is(href === `/${T}/disconnects/${CASE_CUT.toUpperCase()}/reconnect`,
    "S148 · and it points at the reconnect SCREEN, by its case number and never by an account id",
    String(href));
  const warnOwed = await p.getByTestId("disconnect-record-warnings").innerText().catch(() => "");
  is(warnOwed.includes("Money is still owed."),
    "BR-CUS-1097 · and the money is STATED — shown, not collected first",
    warnOwed || "(no warnings list)");
  await p.screenshot({ path: `${SHOTS}/${width}-reconnect-owing.png`, fullPage: true });

  // ⚠ **NO HORIZONTAL SCROLL AT EITHER WIDTH** — the staff app must work at 1280.
  const overflow = await p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  is(overflow <= 0, `the page does not scroll sideways at ${width}px`, `overflow=${overflow}px`);

  if (WRITE_HOLD && width === 1440) {
    console.log("  … --hold given: recording a real protection and re-reading the state chip");
    await p.getByRole("button", { name: "Hold the case" }).first().click();
    await p.waitForTimeout(600);
    await p.getByText("Medical certificate").first().click();
    await p.fill("#disconnect-hold-review-on", "2026-12-31");
    await p.locator("[role=dialog]").getByRole("button", { name: "Hold the case" }).click();
    await p.waitForTimeout(1500);
    await record(p, CASE_SCHEDULED);
    const head = await p.locator("main").innerText();
    is(head.includes("On hold"), "DEF-CUS-6755 · the record reads `On hold` after a real hold", head.slice(0, 300));
  }

  await p.context().close();
}

await browser.close();
console.log(`\n${pass} passed, ${failures.length} failed`);
for (const f of failures) console.log(`  ✗ ${f}`);
for (const e of pageErrors) console.log(`  ⚠ ${e}`);
process.exit(failures.length === 0 && pageErrors.length === 0 ? 0 : 1);
