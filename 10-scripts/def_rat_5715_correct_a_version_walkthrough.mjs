// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-RAT-5715 — BR-RAT-104's shared rule was built for taxes only, so
//          a typo in a live rate schedule had no correction path at all.
// Rules:   BR-RAT-104 (a correction restates the SAME window) · BR-RAT-037 (a
//          CHANGE is a new row with a NEW window) · hard rule 4 (a bill locks
//          at issue) · B14 rule 32/33 (the copy caps)
// ───────────────────────────────────────────────────────
/**
 * Fix a typo in a rate that is already billing customers, in a real browser,
 * and prove the four things that make it a correction rather than a change.
 *
 *     BASE=http://127.0.0.1:8380 node 10-scripts/def_rat_5715_correct_a_version_walkthrough.mjs
 *
 * ⚠ **THE FOURTH CHECK IS THE ONE THAT MATTERS.** Steps 1–3 prove the feature is
 * reachable and says the right words. Step 4 reads the schedule's own detail
 * page afterwards and asserts the WINDOW did not move — because a "correction"
 * that opened a new window would be a rate change wearing a correction's
 * clothes, and it would silently rewrite which bills the old figure was ever
 * right for. Every screen would look perfectly normal.
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
const apiCalls = [];
// ⚠ **THE CORRECTION CALL IS WATCHED BY ITSELF, AND THAT IS NOT BELT AND
// BRACES.** The first draft of this script asserted only that the window had
// not moved after committing — and the window does not move when the commit is
// REFUSED either. It printed "ALL CHECKS PASSED" over a `404`. That is
// hard-won law 7's *"ask what would make this check pass wrongly"*, in a
// walkthrough written to obey law 6. A check whose pass and whose no-op look
// identical is worse than no check, because it is trusted.
let correctCall = null;
page.on("response", async (r) => {
  const u = new URL(r.url());
  if (u.pathname.includes("/rate-schedules/")) {
    apiCalls.push(`${r.request().method()} ${u.pathname} -> ${r.status()}`);
    if (u.pathname.endsWith("/corrections") && r.request().method() === "POST") {
      let body = "";
      try { body = (await r.text()).slice(0, 400); } catch {}
      correctCall = { status: r.status(), body };
    }
  }
});

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await Promise.all([
  page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
  page.click('button[type="submit"]'),
]);
note(`signed in as ${EMAIL}`);

// ── 0 · a schedule that is LIVE ────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/plans-rates/rates`, { waitUntil: "domcontentloaded" });
await page.waitForTimeout(2000);
const liveRow = page.locator("table tbody tr", { hasText: "Active" }).first();
if (!(await liveRow.count())) {
  fail("no ACTIVE rate schedule — nothing to correct");
  await browser.close();
  process.exit(1);
}
note(`\n0 · ${(await liveRow.innerText()).replace(/\s+/g, " ").trim()}`);
await liveRow.locator("button.rating-link, a").first().click();
await page.waitForTimeout(2000);
const detailUrl = page.url();
const tariffId = detailUrl.split("/rates/")[1]?.split(/[/?#]/)[0] ?? "";
const datesOf = (text) => (text.match(/\d{2}\/\d{2}\/\d{4}/g) ?? []).join(" ");
const windowBefore = datesOf((await page.locator("body").innerText()).replace(/\s+/g, " "));
note(`    dates on the detail page before: ${windowBefore || "(none found)"}`);

// ── 1 · the question is asked ─────────────────────────────────────────────
note("\n1 · DEF-RAT-5715 2.4 — the wizard asks what this edit IS");
await page.goto(`${BASE}/${TENANT}/plans-rates/rates/${tariffId}/edit`, {
  waitUntil: "domcontentloaded",
});
await page.waitForTimeout(2500);
await page.screenshot({ path: `${SHOTS}/rat5709_1_intent.png`, fullPage: true });
const body1 = (await page.locator("body").innerText()).replace(/\s+/g, " ");
if (/Fix an error/i.test(body1) && /Change the rate/i.test(body1)) {
  ok("both answers are offered, in words");
} else {
  fail("the wizard does not ask — a typo still has to be filed as a rate change");
}
if (/A new price, from a date/i.test(body1)) {
  ok("the chosen answer carries one fact");
} else {
  fail("no fact under the chosen answer");
}

// ── 2 · choose Fix an error ───────────────────────────────────────────────
note("\n2 · choose it, and see what it says about bills already sent");
// ⚠ CLICK THE LABEL, NOT THE INPUT. `SegmentedField` draws the standard
// accessible pattern — a visually hidden `<input type="radio">` inside a
// `<label class="seg-opt">` whose `<span>` carries the paint. `getByRole` finds
// the input and playwright refuses to click it because it is not visible, which
// is correct: a person clicks the thing they can see.
const fixOption = page.locator("label.seg-opt", { hasText: "Fix an error" }).first();
if (await fixOption.count()) {
  await fixOption.click();
} else {
  await page.getByText(/Fix an error/i).first().click();
}
await page.waitForTimeout(900);
await page.screenshot({ path: `${SHOTS}/rat5709_2_correcting.png`, fullPage: true });
const body2 = (await page.locator("body").innerText()).replace(/\s+/g, " ");
if (/Same dates\. The price was wrong\./i.test(body2)) {
  ok("the fact changes with the answer");
} else {
  fail("choosing Fix an error changed no sentence on screen");
}
// 2.5 — the count, in one of its THREE honest forms.
if (
  /bills already went out/i.test(body2) ||
  /No bills went out on this/i.test(body2) ||
  /could not count the bills/i.test(body2)
) {
  ok("it says what the correction cannot reach (hard rule 4)");
} else {
  fail("nothing says whether bills have already gone out on this price");
}

// ── 3 · walk to the end and look at step 4 ────────────────────────────────
note("\n3 · step 4 asks for the reason and NOT for a date");
for (let step = 0; step < 3; step += 1) {
  const cont = page.getByRole("button", { name: /^Continue$/ }).first();
  if (await cont.count()) {
    await cont.click().catch(() => {});
    await page.waitForTimeout(800);
  }
}
await page.screenshot({ path: `${SHOTS}/rat5709_3_step4.png`, fullPage: true });
const step4 = (await page.locator("body").innerText()).replace(/\s+/g, " ");
const dateInputs = await page.locator('input[type="date"]').count();
if (/What was wrong/i.test(step4)) {
  ok("it asks what was typed wrongly");
} else {
  fail("step 4 does not ask for a correction reason");
}
if (dateInputs === 0) {
  ok("no date field is offered — the window is the corrected row's");
} else {
  fail(`${dateInputs} date field(s) on a correction — a correction keeps its window`);
}

// ── 4 · commit, then read the window back ─────────────────────────────────
note("\n4 · ⚠ THE ONE THAT MATTERS — the window must not have moved");
const reason = page.locator("#rate-correction-reason");
if (await reason.count()) {
  await reason.fill("Tier 1 was typed wrongly and the board approved the lower figure");
  await page.waitForTimeout(400);
}
const cont = page.getByRole("button", { name: /^Continue$/ }).first();
if (await cont.count()) {
  await cont.click().catch(() => {});
  await page.waitForTimeout(1200);
}
await page.screenshot({ path: `${SHOTS}/rat5709_4_review.png`, fullPage: true });
const commit = page.getByRole("button", { name: /Correct this version/i }).first();
if (await commit.count()) {
  ok('the commit says "Correct this version"');
  await commit.click();
  await page.waitForTimeout(3000);
  await page.screenshot({ path: `${SHOTS}/rat5709_5_committed.png`, fullPage: true });
  if (correctCall === null) {
    fail("the commit was pressed and NO correction call was made at all");
  } else if (correctCall.status >= 400) {
    fail(`the correction was REFUSED ${correctCall.status}: ${correctCall.body}`);
  } else {
    ok(`the correction was accepted (${correctCall.status})`);
  }
} else {
  fail("no Correct this version commit — the correction cannot be made from the screen");
}

await page.goto(detailUrl, { waitUntil: "domcontentloaded" });
await page.waitForTimeout(2500);
await page.screenshot({ path: `${SHOTS}/rat5709_6_detail_after.png`, fullPage: true });
const windowAfter = datesOf((await page.locator("body").innerText()).replace(/\s+/g, " "));
if (windowAfter === windowBefore) {
  ok(`the window did not move: ${windowAfter}`);
} else {
  fail(`THE WINDOW MOVED — that is a rate change, not a correction: ${windowBefore} -> ${windowAfter}`);
}
// ⚠ AND THE POSITIVE HALF: a correction row must now EXIST. Without this, "the
// window did not move" is satisfied perfectly by nothing having happened.
const detail = await page.evaluate(async (t) => {
  const r = await fetch(`/api/${t}/rate-schedules/${location.pathname.split("/rates/")[1].split(/[/?#]/)[0]}`);
  return r.ok ? await r.json() : null;
}, TENANT);
const versions = detail?.versions ?? [];
const correction = versions.find((v) => v && v.corrects !== null);
const superseded = versions.find((v) => v && v.superseded_by !== null);
if (correction && superseded) {
  ok(`a correction row exists and the old one is superseded (reason: "${correction.correction_reason}")`);
  if (correction.effective_from === superseded.effective_from) {
    ok("both rows carry the SAME window — which is what makes it a correction");
  } else {
    fail(`the two rows do not share a window: ${superseded.effective_from} vs ${correction.effective_from}`);
  }
} else {
  fail("no correction row on the schedule — the commit changed nothing");
}

console.log("\nAPI:\n  " + apiCalls.join("\n  "));
console.log(
  problems.length === 0
    ? "\nALL CHECKS PASSED"
    : `\n${problems.length} PROBLEM(S):\n - ${problems.join("\n - ")}`,
);
await browser.close();
process.exit(problems.length === 0 ? 0 : 1);
