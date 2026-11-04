// ── Trace ──────────────────────────────────────────────
// Defects: DEF-RAT-6447 (a live rate schedule offered NO way to save an
//          unfinished edit) · DEF-RAT-6448 (a parked draft was served and
//          never loaded) · DEF-055 (the wizard's success toasts were in no
//          catalogue for 37 days)
// Rules:   BR-RAT-031 (save-draft resumable) · BR-RAT-037 (an IN-FORCE version
//          is never edited in place — the row, not the schedule) ·
//          B14 rule 6 (danger tier on a destructive commit) · rule 21
//          (Tailwind only) · rule 33 (a fact is six words)
// Note:    the Plans & Rates blueprint p048 DRAWS this bar on a live schedule —
//          "New version of Sample — Residential water", `Cancel` and
//          `Save draft & exit`. The button was drawn and not built.
// ───────────────────────────────────────────────────────
/**
 * Park a draft on a rate schedule that is already billing customers, walk away,
 * come back, and throw it away — in a real browser.
 *
 *     BASE=http://127.0.0.1:8380 node 10-scripts/def_rat_5680_park_a_draft_walkthrough.mjs
 *
 * ⚠ **THIS IS THE ONLY CHECK THAT CAN SEE THE THING THAT WAS BROKEN.**
 * `RateScheduleWizard` is never mounted whole in the vitest suite — it gates on
 * `detailQuery.isPending`, so under `renderToStaticMarkup` it renders the
 * loading skeleton and nothing else. 1,505 lines of unit tests, 58 cases, and
 * not one of them can see this component's own action bar. That is precisely
 * how a button the blueprint drew came to be absent from the product with every
 * check green (hard-won law 6).
 *
 * ⚠ **AND THE ASSERTION THAT MATTERS IS THE MONEY ONE.** Step 5 reads the LIVE
 * rate back off the schedule's own detail page after the draft is parked. A
 * walkthrough that only proved the button exists would pass over a fix that
 * saved the draft by overwriting the rate customers pay.
 */
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8380";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const SHOTS = process.env.SHOTS ?? "/tmp";

const problems = [];
const note = (m) => console.log(m);
const fail = (m) => { problems.push(m); console.log("  ✗ " + m); };
const ok = (m) => console.log("  ✓ " + m);

const browser = await chromium.launch({
  ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
});
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
const page = await ctx.newPage();

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await Promise.all([
  page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
  page.click('button[type="submit"]'),
]);
note(`signed in as ${EMAIL}`);

// ── 0 · find a schedule that is LIVE ───────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/plans-rates/rates`, { waitUntil: "domcontentloaded" });
await page.waitForTimeout(2000);
const liveRow = page.locator("table tbody tr", { hasText: "Active" }).first();
if (!(await liveRow.count())) {
  fail("no ACTIVE rate schedule on this tenant — nothing to reproduce against");
  await browser.close();
  process.exit(1);
}
const rowText = (await liveRow.innerText()).replace(/\s+/g, " ").trim();
note(`\n0 · the schedule under test — ${rowText}`);
// The name cell is a BUTTON, not a link (the list navigates in-app).
await liveRow.locator("button.rating-link, a").first().click();
await page.waitForTimeout(2000);
const detailUrl = page.url();
const tariffId = detailUrl.split("/rates/")[1]?.split(/[/?#]/)[0] ?? "";

// The live prices, read off the product BEFORE anything is parked.
const liveBefore = (await page.locator("body").innerText()).replace(/\s+/g, " ");
const priceOf = (text) => (text.match(/\d+\.\d{2}/g) ?? []).join(" ");
const livePricesBefore = priceOf(liveBefore);
note(`    live figures on the detail page: ${livePricesBefore || "(none found)"}`);

// ── 1 · the button the blueprint draws ─────────────────────────────────────
note("\n1 · DEF-RAT-6447 — Save draft & exit, on a schedule that is already live");
await page.goto(`${BASE}/${TENANT}/plans-rates/rates/${tariffId}/edit`, {
  waitUntil: "domcontentloaded",
});
await page.waitForTimeout(2500);
await page.screenshot({ path: `${SHOTS}/rat5680_1_wizard_live.png`, fullPage: true });
const saveDraft = page.getByRole("button", { name: /Save draft/i }).first();
if (await saveDraft.count()) {
  ok(`"Save draft & exit" is on screen (blueprint p048 draws it here)`);
  if (await saveDraft.isDisabled()) fail("…and it is DISABLED — a dead control is not a door");
} else {
  fail(`"Save draft & exit" is NOT on screen — the deadlock the PO reported`);
}

// ── 2 · type a change and park it ──────────────────────────────────────────
note("\n2 · type something and press it");
// Walk to the Rates step the way a clerk does — the rail only goes backwards.
for (let step = 0; step < 2; step += 1) {
  const cont = page.getByRole("button", { name: /^Continue$/ }).first();
  if (await cont.count()) {
    await cont.click().catch(() => {});
    await page.waitForTimeout(900);
  }
}
const firstPrice = page.locator('input[type="text"], input[type="number"]').last();
let typed = "";
if (await firstPrice.count()) {
  typed = "9.99";
  await firstPrice.fill(typed);
  await page.waitForTimeout(400);
  ok(`typed ${typed} into the last price box`);
}
await page.screenshot({ path: `${SHOTS}/rat5680_2_typed.png`, fullPage: true });
const sd = page.getByRole("button", { name: /Save draft/i }).first();
if (await sd.count()) {
  await sd.click();
  await page.waitForTimeout(2500);
  const after = (await page.locator("body").innerText()).replace(/\s+/g, " ");
  await page.screenshot({ path: `${SHOTS}/rat5680_3_after_save.png`, fullPage: true });
  if (/already in force|can't be edited|cannot be edited/i.test(after)) {
    fail("the server still refuses the save — BR-RAT-037 guard not fixed");
  } else {
    ok("the save was accepted");
  }
  // DEF-055 — the toast must be a sentence, never the raw key.
  if (/rating\.rate\.toast/.test(after)) {
    fail("the success toast rendered its own KEY — DEF-055 is back");
  } else {
    ok("no raw catalogue key on screen");
  }
}

// ── 3 · reopen: DEF-RAT-6448, the draft must be what comes back ────────────
note("\n3 · DEF-RAT-6448 — reopen, and see YOUR draft rather than the live rate");
await page.goto(`${BASE}/${TENANT}/plans-rates/rates/${tariffId}/edit`, {
  waitUntil: "domcontentloaded",
});
await page.waitForTimeout(2500);
await page.screenshot({ path: `${SHOTS}/rat5680_4_reopened.png`, fullPage: true });
const reopened = (await page.locator("body").innerText()).replace(/\s+/g, " ");
if (/draft/i.test(reopened)) {
  ok("the screen says which of the two rows it is showing");
} else {
  fail("nothing on screen says whether this is the live rate or the parked draft");
}
const discard = page.getByRole("button", { name: /Discard draft/i }).first();
if (await discard.count()) {
  ok("a way OUT of the parked draft exists");
} else {
  fail("no Discard control — the one-draft constraint traps stale work");
}

// ── 4 · the live rate has not moved ────────────────────────────────────────
note("\n4 · the money check — what customers pay must be untouched");
await page.goto(detailUrl, { waitUntil: "domcontentloaded" });
await page.waitForTimeout(2000);
const livePricesAfter = priceOf((await page.locator("body").innerText()).replace(/\s+/g, " "));
await page.screenshot({ path: `${SHOTS}/rat5680_5_detail_after.png`, fullPage: true });
if (livePricesAfter === livePricesBefore) {
  ok(`the live figures are unchanged: ${livePricesAfter}`);
} else {
  fail(`THE LIVE RATE MOVED: ${livePricesBefore}  →  ${livePricesAfter}`);
}

// ── 5 · discard it, behind the danger tier ─────────────────────────────────
note("\n5 · discard the draft — B14 rule 6, a destructive commit");
await page.goto(`${BASE}/${TENANT}/plans-rates/rates/${tariffId}/edit`, {
  waitUntil: "domcontentloaded",
});
await page.waitForTimeout(2500);
const discard2 = page.getByRole("button", { name: /Discard draft/i }).first();
if (await discard2.count()) {
  await discard2.click();
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `${SHOTS}/rat5680_6_confirm.png`, fullPage: true });
  const dialog = page.locator('[role="alertdialog"]');
  if (await dialog.count()) {
    ok("it asks first, in an alertdialog");
    const confirm = dialog.getByRole("button", { name: /Discard draft/i }).last();
    await confirm.click();
    await page.waitForTimeout(2500);
    await page.screenshot({ path: `${SHOTS}/rat5680_7_discarded.png`, fullPage: true });
    const gone = page.getByRole("button", { name: /Discard draft/i });
    if ((await gone.count()) === 0) {
      ok("the draft is gone and the control went with it");
    } else {
      fail("the discard control is still on screen after discarding");
    }
  } else {
    fail("discard committed with no confirmation — B14 rule 6");
  }
}

// ── 6 · the live rate, one more time ───────────────────────────────────────
await page.goto(detailUrl, { waitUntil: "domcontentloaded" });
await page.waitForTimeout(2000);
const liveFinal = priceOf((await page.locator("body").innerText()).replace(/\s+/g, " "));
if (liveFinal === livePricesBefore) {
  ok(`still unchanged after the discard: ${liveFinal}`);
} else {
  fail(`THE LIVE RATE MOVED ON DISCARD: ${livePricesBefore}  →  ${liveFinal}`);
}

console.log(
  problems.length === 0
    ? "\nALL CHECKS PASSED"
    : `\n${problems.length} PROBLEM(S):\n - ${problems.join("\n - ")}`,
);
await browser.close();
process.exit(problems.length === 0 ? 0 : 1);
