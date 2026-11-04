// ── Trace ──────────────────────────────────────────────
// Defects: DEF-TEN-5842 (SET-06 step 1 drew ONE area control under a label
//          reading `Area · sub-area`; the PO ruled TWO on 2026-09-08 and the
//          ruling never reached this wizard) · DEF-TEN-5843 (the premises
//          picker ignored the area step 1 had just asked for) ·
//          DEF-TEN-5840 / DEF-TEN-5840 (no `Select all` on the cycle wizard
//          or on the units list) · DEF-MET-5841 (the premises list's eye icon
//          opened the UNITS tab, not the premise)
// Rules:   BR-MET-071 (two controls, ONE stored column) · BR-MET-072 (the area
//          filter is MULTI-SELECT; a parent matches its sub-areas) ·
//          BR-MET-073 (a route carries ONE area) · BR-MET-041 (bulk plan
//          assignment) · NFR-3 (server pagination) · B14 rule 9 (chips, never
//          a wall of checkboxes) · rule 15 (icon row actions)
//          · CLAUDE.md hard-won law 6 — NO GATE IN THIS REPO READS RENDERED
//          OUTPUT, so this is the only instrument that can see any of it.
// ───────────────────────────────────────────────────────
/**
 * Walk the four fixes the human QA team reported on 2026-09-19, in a real
 * browser, and read what is DRAWN.
 *
 *     QA_BASE=http://127.0.0.1:8147 \
 *       node 10-scripts/qa_20260919_routes_premises_walkthrough.mjs
 *
 * ⚠ **27 vitest cases, a clean `tsc` and a clean `eslint` pass on this change
 * already.** Not one of them can see a locale key that renders blank, a select
 * whose options never arrive, a chip that lays out on top of the toolbar, or a
 * control that is present and dead — hard-won law 2, the class this repo keeps
 * paying for.
 *
 * ⚠ **IT REFUSES A STALE BUILD, AND THAT GUARD IS COPIED ON PURPOSE.** On
 * 2026-09-19 a sibling walk ran against a `dist/` built 26 hours earlier:
 * three fixes that ARE on the branch read as ABSENT and the walk was one step
 * from reporting that other lanes had not done their work. Nothing in the page
 * says how old it is, and `tsc`, the suites and every gate are green either
 * way because none of them look at `dist/`. A walk against a stale bundle is
 * worse than no walk — it produces confident, specific, WRONG findings about
 * other people's work.
 *
 * ⚠ **SELECTORS LIE QUIETLY, SO THIS ASSERTS ON WHAT THE DOM ACTUALLY IS.** A
 * premises row opens through `<button class="rating-link">` and NOT through an
 * anchor, so a probe looking for `a[href*=…]` reports the feature missing and
 * is believed. Every check below names the element it found, and the eye-icon
 * check asserts an ABSENCE by two independent routes rather than one.
 *
 * Credentials and the restore procedure: see
 * `10-scripts/def_rat_5731_plan_tables_walkthrough.mjs`'s header. The
 * easily-forgotten half is the ACTIVE `TenantMembership` carrying
 * `system_admin` — without it sign-in succeeds and every screen is empty.
 */
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");
import { execSync } from "node:child_process";
import { statSync, mkdirSync } from "node:fs";

const BASE = process.env.QA_BASE || "http://127.0.0.1:8147";
const TENANT = process.env.QA_TENANT || "brazosbend";
const EMAIL = process.env.QA_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.QA_PASSWORD || "S3cure!passw0rd";
const CHROME = process.env.QA_CHROME
  || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const SHOTS = process.env.QA_SHOTS || "/tmp/qa678-shots";

// ── the staleness refusal ──────────────────────────────────────────────────
const built = statSync("07-frontend/dist/index.html").mtime;
const newestSrc = new Date(
  execSync("git log -1 --format=%cI -- 07-frontend/src").toString().trim(),
);
if (built < newestSrc) {
  console.error(
    `REFUSED: dist/ was built ${built.toISOString()} but 07-frontend/src has a\n` +
    `commit at ${newestSrc.toISOString()}. Run \`npx vite build\` first.\n` +
    `A walk against a stale bundle reports absent features that are present.`,
  );
  process.exit(2);
}
// ⚠ **AND THE COMMIT DATE IS NOT ENOUGH — THE GUARD COULD PASS OVER AN
// UNCOMMITTED FIX (`DEF-MET-5855`'s lane, 2026-09-19).** `git log` answers for
// the last COMMIT of `07-frontend/src`; a lane proving its own change has that
// change on DISK and not in a commit, so a `dist/` built before the edit is
// newer than the last commit and the refusal above cannot fire. The walk then
// reports the lane's own fix as absent — the same confident-and-wrong finding,
// arriving through the one door the first guard left open. So the WORKING TREE
// is asked as well, and the newer of the two decides.
const newestFile = new Date(Number(
  execSync("find 07-frontend/src -type f -newermt '@0' -printf '%T@\\n' | sort -n | tail -1")
    .toString().trim() || 0) * 1000);
const newestSrcAny = newestFile > newestSrc ? newestFile : newestSrc;
if (built < newestSrcAny) {
  console.error(
    `REFUSED: dist/ was built ${built.toISOString()} but 07-frontend/src has a\n` +
    `file written at ${newestSrcAny.toISOString()}. Run \`npx vite build\` first.`,
  );
  process.exit(2);
}
console.log(`dist/ built ${built.toISOString()} — newer than src's last commit AND its newest file. OK.\n`);

mkdirSync(SHOTS, { recursive: true });

const problems = [];
const ok = (m) => console.log("  ✓ " + m);
const fail = (m) => { problems.push(m); console.log("  ✗ " + m); };
const head = (m) => console.log("\n" + m);

const browser = await chromium.launch({ executablePath: CHROME });
const ctx = await browser.newContext({ viewport: { width: 1500, height: 1100 } });
const page = await ctx.newPage();
page.on("pageerror", (e) => fail(`PAGE ERROR: ${e.message}`));

/** Every `/routes/premises-picker` request the page makes, with its `area`s —
 *  the only way to see QA 8, because a row count cannot distinguish a picker
 *  that narrowed from one that was handed three rows anyway. */
const pickerCalls = [];
page.on("request", (r) => {
  const url = r.url();
  if (url.includes("/routes/premises-picker")) {
    pickerCalls.push(new URL(url).searchParams.getAll("area"));
  }
});

const shot = async (name) => {
  await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: false });
};
const settle = async (ms = 900) => { await page.waitForTimeout(ms); };

/**
 * Fill the wizard's **Name** box.
 *
 * ⚠ **NEITHER WIZARD'S INPUTS CARRY AN `id`, AND `input` FIRST IS THE SHELL'S
 * SEARCH BOX.** A first draft of this walk used `page.locator("input").first()`
 * and filled the app-shell search, so Name stayed empty, `Continue` refused,
 * and step 2 never rendered — at which point the walk reported `Select all` as
 * MISSING on a screen that has had it since CR-006. That is precisely the
 * confident-and-wrong finding the staleness guard above exists to prevent,
 * arriving through a different door. The box is found by the text of the
 * `<label>` that wraps it.
 */
async function fillName(value) {
  const box = page.locator("label", { hasText: /^Name/ }).locator("input").first();
  await box.waitFor({ state: "visible", timeout: 15000 });
  await box.fill(value);
  const got = await box.inputValue();
  if (got !== value) { fail(`could not type into the Name box (it holds "${got}")`); }
  return got === value;
}

/** Press Continue and REFUSE to carry on pretending if the step did not move —
 *  a walk that goes quiet here reports every later control as absent. */
async function continueFrom(stepName) {
  await page.getByRole("button", { name: /^Continue$/ }).click();
  await settle(2500);
  const blocked = await page.locator('[data-rcw="error"], [role="alert"]').count();
  if (blocked > 0) {
    const why = (await page.locator('[data-rcw="error"], [role="alert"]').first().textContent()) ?? "";
    fail(`${stepName}: Continue was REFUSED — "${why.trim()}". Everything after this is unmeasured.`);
    return false;
  }
  return true;
}

// ── sign in ────────────────────────────────────────────────────────────────
head("SIGN IN");
// ⚠ **THE ROUTE IS `/signin`, ONE WORD, AND THE FIELDS ARE `#signin-email` /
// `#signin-password`.** `input[type="email"]` finds nothing here and the walk
// dies at the door — a selector that lies quietly, which is what this whole
// script exists to avoid doing to other people's work.
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await settle(1200);
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await Promise.all([
  page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
  page.click('button[type="submit"]'),
]);
await settle(1500);
ok(`signed in — now at ${new URL(page.url()).pathname}`);

// ═══════════════════════════════════════════════════════════════════════════
// QA 6 · Area and sub-area are TWO controls on the route wizard
// ═══════════════════════════════════════════════════════════════════════════
head("QA 6 — SET-06 step 1: Area and Sub-area are two controls (DEF-TEN-5842)");
await page.goto(`${BASE}/${TENANT}/settings/reference-data/routes-cycles/routes/new`, {
  waitUntil: "domcontentloaded",
});
await settle(2500);
await shot("qa6-step1");

const topSel = page.locator('select[data-rcw="area-top"]');
const subSel = page.locator('select[data-rcw="area-sub"]');
if (await topSel.count() === 1) { ok("the AREA select is drawn"); }
else { fail(`expected exactly one area select, found ${await topSel.count()}`); }
if (await subSel.count() === 1) { ok("the SUB-AREA select is drawn — the control QA said was missing"); }
else { fail(`expected exactly one sub-area select, found ${await subSel.count()}`); }

// BR-SHL-025 — present and disabled WITH its reason, never absent and never dead.
if (await subSel.count() === 1) {
  const disabled = await subSel.isDisabled();
  const title = await subSel.getAttribute("title");
  if (disabled) { ok("sub-area starts DISABLED (no area chosen yet)"); }
  else { fail("sub-area is enabled with no area chosen — it can post a code that contradicts the box above"); }
  if (title && title.trim() !== "") { ok(`…and says why: "${title}"`); }
  else { fail("sub-area is disabled with NO reason on it (BR-SHL-025)"); }
}

// The options must actually ARRIVE from the server — a select with one empty
// option is the shape of a picker whose lookup never resolved.
const topOptions = await topSel.locator("option").allTextContents();
if (topOptions.length > 1) { ok(`area offers ${topOptions.length - 1} district(s): ${topOptions.slice(1).join(", ")}`); }
else { fail("the area select has no options — the areas lookup did not arrive"); }

// Choosing a district must fill the sub-area box with ITS children only.
const district = topOptions.find((o, i) => i > 0 && o.trim() !== "");
if (district) {
  await topSel.selectOption({ label: district });
  await settle(900);
  const subOptions = (await subSel.locator("option").allTextContents()).slice(1);
  const nowDisabled = await subSel.isDisabled();
  if (!nowDisabled) { ok(`choosing "${district}" ENABLES the sub-area box`); }
  else { fail(`sub-area still disabled after choosing "${district}"`); }
  console.log(`      sub-areas offered under "${district}": ${subOptions.length ? subOptions.join(", ") : "(none — this district is childless, which is the ratified fixture)"}`);
  // Never a district in the sub-area box.
  const leaked = subOptions.filter((s) => topOptions.includes(s));
  if (leaked.length === 0) { ok("no district leaks into the sub-area box"); }
  else { fail(`districts appearing as sub-areas: ${leaked.join(", ")}`); }
  // ⚠ **THE EMPTY OPTION MUST SAY `No sub-area`, NOT `No area`.** The first cut
  // reused the Area box's own string, so with `Downtown` chosen above the box
  // beside it read *No area* — a contradiction on one row of one form, invisible
  // to `tsc`, to 27 vitest cases and to every gate, and found only by looking.
  const subEmpty = (await subSel.locator("option").first().textContent())?.trim();
  if (subEmpty === "No sub-area") { ok(`the sub-area's empty option reads "${subEmpty}"`); }
  else { fail(`the sub-area's empty option reads "${subEmpty}" — it must not borrow the Area box's wording`); }
  await shot("qa6-step1-area-chosen");
}

// ═══════════════════════════════════════════════════════════════════════════
// QA 8 · the picker DEFAULTS to the area step 1 chose — visibly, reversibly
// ═══════════════════════════════════════════════════════════════════════════
head("QA 8 — SET-06 step 2: the picker opens on step 1's area (DEF-TEN-5843)");
await fillName("QA walk route");
await continueFrom("SET-06 step 1");
await shot("qa8-step2");

/** What the pager says the filters match — `1–12 of 12` → 12. */
async function matchTotal() {
  const txt = (await page.locator("text=/of [0-9,]+/").first().textContent().catch(() => "")) ?? "";
  return Number((txt.match(/of\s+([0-9][0-9,]*)/)?.[1] ?? "-1").replace(/,/g, ""));
}

// ⚠ **THE REQUEST IS THE ASSERTION, AND IT IS READ FROM THE WHOLE HISTORY
// RATHER THAN FROM "WHAT HAPPENED AFTER Continue".** A first draft looked only
// at requests issued after the press and found none — correctly, because the
// picker query is NOT gated on the step, so the narrowed fetch has already
// happened by the time the clerk leaves step 1, and React Query then serves
// the rest from cache. The draft therefore reported *"the picker did not load
// at all"* over a picker that had loaded, narrowed, twice. Counting rendered
// rows cannot stand in for this either: N rows appear whether the browser
// asked for N or for forty thousand.
const narrowed = pickerCalls.filter((areas) => areas.length > 0);
if (narrowed.length > 0) {
  ok(`the picker asked the server for area(s) [${narrowed.at(-1).join(", ")}] — it is narrowed by step 1`);
} else {
  fail("every premises-picker request carried NO area — step 1's answer was thrown away (the reported defect)");
}
const narrowedTotal = await matchTotal();
console.log(`      with the area applied the pager reads: ${narrowedTotal} matching`);

// …and the narrowing must be VISIBLE, as a removable chip.
const chips = await page.locator("[data-chip-remove], button[aria-label^='Remove the']").count();
const chipText = await page.locator("text=/Area:/").count();
if (chipText > 0) { ok("the applied area is drawn as a CHIP, so a clerk can read why the list is short"); }
else { fail("no area chip on screen — the narrowing is invisible"); }

// …and REVERSIBLE. Removing the chip must widen the request back to the tenant.
const removeChip = page.locator("button[aria-label^='Remove the']").first();
if (await removeChip.count() > 0) {
  await removeChip.click();
  await settle(2200);
  // ⚠ **ASSERTED ON THE SCREEN, NOT ON A NEW REQUEST.** React Query already
  // holds the unfiltered page from this wizard's first render, so widening is
  // legitimately served from cache and NO request goes out. A check waiting
  // for one reports a working control as broken — law 7's "what would make
  // this fail wrongly", which is the same question upside down.
  const widerTotal = await matchTotal();
  const chipGone = (await page.locator("button[aria-label^='Remove the']").count()) === 0;
  if (chipGone) { ok("the chip is removable and comes off"); }
  else { fail("the area chip survived its own remove button"); }
  if (widerTotal > narrowedTotal) {
    ok(`removing it WIDENS the list: ${narrowedTotal} → ${widerTotal} matching — a default, not a lock`);
  } else {
    fail(`removing the chip did not widen the list (${narrowedTotal} → ${widerTotal})`);
  }
  await shot("qa8-widened");
} else {
  fail(`no removable area chip found (found ${chips} chip-remove control(s))`);
}

// …and a second area can be ADDED — the street that crosses two areas.
const addFilter = page.locator('select[aria-label*="Filter"], select[aria-label*="filter"]').first();
if (await addFilter.count() > 0) {
  const opts = await addFilter.locator("option").allTextContents();
  console.log(`      the + Filter control offers: ${opts.slice(1).join(", ") || "(nothing)"}`);
  if (opts.length > 2) {
    const n = pickerCalls.length;
    await addFilter.selectOption({ index: opts.length - 1 });
    await settle(1500);
    await addFilter.selectOption({ index: 1 }).catch(() => {});
    await settle(1500);
    const after = pickerCalls.slice(n).at(-1) ?? [];
    if (after.length >= 2) { ok(`two areas applied at once: [${after.join(", ")}] — a route crossing two areas is expressible`); }
    else if (after.length === 1) { ok(`one area applied [${after.join(", ")}]; a second add is available in the control`); }
    else { fail("adding an area from the filter control changed nothing"); }
  }
} else {
  fail("no + Filter add control on the picker (B14 rule 9 wants chips PLUS an add control)");
}

// QA 7, half one — `Select all {n}` on the ROUTE wizard (this one already existed).
head("QA 7a — SET-06 step 2 already had `Select all` (the shape the others copy)");
const routeSelectAll = page.getByRole("button", { name: /Select all/i });
if (await routeSelectAll.count() > 0) {
  ok(`route wizard: "${(await routeSelectAll.first().textContent())?.trim()}"`);
} else {
  fail("the route wizard's Select all is gone — this lane must not have removed it");
}

// ═══════════════════════════════════════════════════════════════════════════
// QA 7 · `Select all {n}` on the CYCLE wizard
// ═══════════════════════════════════════════════════════════════════════════
head("QA 7b — SET-07 step 2: `Select all` on the cycle wizard (DEF-TEN-5840)");
await page.goto(`${BASE}/${TENANT}/settings/reference-data/routes-cycles/cycles/new`, {
  waitUntil: "domcontentloaded",
});
await settle(2500);
await fillName("QA walk cycle");
await continueFrom("SET-07 step 1");
await shot("qa7-cycle-step2");

const cycleSelectAll = page.getByRole("button", { name: /Select all/i });
if (await cycleSelectAll.count() > 0) {
  const label = (await cycleSelectAll.first().textContent())?.trim() ?? "";
  ok(`the cycle wizard now has it: "${label}"`);
  // ⚠ **THE NUMBER IS THE CHECK.** A control reading "Select all 50" over a
  // filter matching thousands is the data-loss trap this exists to prevent, so
  // the label is compared against the table's own footer total.
  const footer = (await page.locator("text=/of [0-9,]+/").first().textContent().catch(() => "")) ?? "";
  console.log(`      pager says: "${footer.trim()}"`);
  const stated = Number((label.match(/([0-9][0-9,]*)/)?.[1] ?? "0").replace(/,/g, ""));
  const rowsOnPage = await page.locator("tbody tr").count();
  if (stated >= rowsOnPage) {
    ok(`it states ${stated}, and the page draws ${rowsOnPage} row(s) — the label is the MATCH total, not the page`);
  } else {
    fail(`Select all states ${stated} but the page draws ${rowsOnPage} rows — the label is reading the page`);
  }
  // …and pressing it must actually select that many.
  await cycleSelectAll.first().click();
  await settle(2500);
  const count = (await page.locator('[data-rcw="count"]').first().textContent().catch(() => "")) ?? "";
  console.log(`      after pressing: "${count.trim()}"`);
  const selected = Number((count.match(/([0-9][0-9,]*)/)?.[1] ?? "0").replace(/,/g, ""));
  if (selected === stated && stated > 0) {
    ok(`pressing it selected all ${selected} — the number on the button is the number selected`);
  } else if (stated === 0) {
    ok("no routes on this tenant to select — the control is present and states zero honestly");
  } else {
    fail(`button said ${stated} but ${selected} were selected`);
  }
  await shot("qa7-cycle-selected");
} else {
  fail("the cycle wizard still has NO Select all (this is the reported defect)");
}

// ═══════════════════════════════════════════════════════════════════════════
// QA 7 · `Select all {n}` on the UNITS list
// ═══════════════════════════════════════════════════════════════════════════
head("QA 7c — S15 units list: `Select all` (DEF-TEN-5840)");
await page.goto(`${BASE}/${TENANT}/premises/units`, { waitUntil: "domcontentloaded" });
await settle(2800);
await shot("qa7-units");

const unitsSelectAll = page.getByRole("button", { name: /Select all/i });
if (await unitsSelectAll.count() > 0) {
  const label = (await unitsSelectAll.first().textContent())?.trim() ?? "";
  ok(`the units list now has it, with NOTHING selected yet: "${label}"`);
  const stated = Number((label.match(/([0-9][0-9,]*)/)?.[1] ?? "0").replace(/,/g, ""));
  const rowsOnPage = await page.locator("tbody tr").count();
  if (stated >= rowsOnPage) {
    ok(`it states ${stated} against ${rowsOnPage} row(s) on this page — the MATCH total`);
  } else {
    fail(`Select all states ${stated} but the page draws ${rowsOnPage} rows`);
  }
  // BR-MET-041 must still hold: a SELECTION unlocks the bulk action.
  const assign = page.getByRole("button", { name: /Assign a plan to these/i });
  if (await assign.count() > 0) {
    const blocked = await assign.first().isDisabled();
    if (blocked) { ok("…and `Assign a plan` is GUARDED while nothing is selected (BR-MET-041 intact)"); }
    else { fail("`Assign a plan` is live with an empty selection — BR-MET-041 broken"); }
  } else {
    fail("no bulk `Assign a plan` control on the units list at all");
  }
  await unitsSelectAll.first().click();
  // ⚠ **THIS WAS A FIXED `settle(3000)` AND IT REPORTED A WORKING CONTROL AS
  // BROKEN (found 2026-09-19 by the DEF-MET-5854/5851 lane, on a red it did
  // not cause).** `Select all {n}` WALKS THE SERVER page by page — that is the
  // whole point of it, because the label is the MATCH total and not the fifty
  // rows on screen — so the bar reads `0 unit(s) selected` for the first
  // second or two and then jumps to the full count. Measured on this tenant:
  // `0` at t=1s, `131` at t=3s, and 131 still at t=30s. A fixed wait that
  // lands in that window prints *"button said 131 but the bar reports 0"* over
  // a control that works, which is worse than no check — and it had already
  // been reported twice as a real failure. So the CONDITION is waited for, and
  // the time it took is PRINTED, so a genuine regression to a stuck 0 still
  // fails here after a stated deadline rather than passing quietly.
  const selectStarted = Date.now();
  await page
    .locator(".met-counts")
    .first()
    .locator(`text=/[1-9][0-9,]* unit/`)
    .first()
    .waitFor({ state: "visible", timeout: 20000 })
    .catch(() => undefined);
  console.log(`      the selection settled after ${Math.round((Date.now() - selectStarted) / 100) / 10}s`);
  const bar = (await page.locator(".met-counts").first().textContent().catch(() => "")) ?? "";
  console.log(`      after pressing: "${bar.replace(/\s+/g, " ").trim()}"`);
  const selected = Number((bar.match(/([0-9][0-9,]*)\s*unit/)?.[1] ?? "0").replace(/,/g, ""));
  if (stated > 0 && selected === stated) {
    ok(`pressing it selected all ${selected} — including the rows NOT on this page`);
  } else if (stated === 0) {
    ok("no units on this tenant — the control states zero honestly");
  } else {
    fail(`button said ${stated} but the bar reports ${selected} selected`);
  }
  const assignNow = page.getByRole("button", { name: /Assign a plan to these/i });
  if (await assignNow.count() > 0 && !(await assignNow.first().isDisabled())) {
    ok("…and the bulk action UNLOCKS once the selection exists");
  } else if (stated > 0) {
    fail("the bulk action is still blocked after Select all");
  }
  await shot("qa7-units-selected");
} else {
  fail("the units list still has NO Select all (this is the reported defect)");
}

// ═══════════════════════════════════════════════════════════════════════════
// #14 · the eye icon is gone from the premises list
// ═══════════════════════════════════════════════════════════════════════════
head("#14 — S14 premises list: the eye icon is REMOVED (DEF-MET-5841)");
await page.goto(`${BASE}/${TENANT}/premises`, { waitUntil: "domcontentloaded" });
await settle(2800);
await shot("def14-premises");

// ⚠ TWO INDEPENDENT ROUTES TO THE SAME ABSENCE. One selector could be wrong
// about the DOM; two disagreeing would be worth knowing about.
const eyeByHref = await page.locator('a[href*="f.premises_id"]').count();
const eyeByLabel = await page.locator('[aria-label*="View units"], [title*="View units"]').count();
if (eyeByHref === 0) { ok("no row link carries `?f.premises_id=` any more"); }
else { fail(`${eyeByHref} row link(s) still point at the units tab`); }
if (eyeByLabel === 0) { ok("no `View units` row action is drawn"); }
else { fail(`${eyeByLabel} \`View units\` control(s) still present`); }

// …and the door the PO said replaces it must actually work.
const firstNumber = page.locator("tbody tr button.rating-link, tbody tr a").first();
if (await firstNumber.count() > 0) {
  const text = (await firstNumber.textContent())?.trim();
  // ⚠ **IT IS A `<button class="rating-link">`, NOT AN ANCHOR.** A probe
  // looking only for `a[href]` reports this door missing and is believed.
  const tag = await firstNumber.evaluate((el) => el.tagName.toLowerCase());
  await firstNumber.click();
  await settle(2500);
  const path = new URL(page.url()).pathname;
  if (/\/premises\/[^/]+$/.test(path) && !path.endsWith("/units")) {
    ok(`the premise number ("${text}", a <${tag}>) opens the PREMISE: ${path}`);
  } else {
    fail(`the premise number went to ${path} — not the premise detail`);
  }
  await shot("def14-premise-detail");
} else {
  fail("no premise row identity control found at all");
}

// …and the units-by-premises path must still EXIST somewhere (the consumer
// check `DEF-CUS-3653` asks for: an absence is invisible to every check here).
await page.goto(`${BASE}/${TENANT}/premises/units`, { waitUntil: "domcontentloaded" });
await settle(2500);
const premisesFilter = await page.locator('#f\\.premises_id, [id="f.premises_id"]').count();
if (premisesFilter > 0) { ok("the units list still owns its own `premises` filter — the path survives the deletion"); }
else { fail("units-filtered-by-premises has NO surviving door — the eye was the only one"); }

// ═══════════════════════════════════════════════════════════════════════════
// QA 9 · Cycle detail → Coverage — the list is the WHOLE UTILITY, and says so
// ═══════════════════════════════════════════════════════════════════════════
//
// ⚠ **REPRODUCED 2026-09-19, AND THE DATA WAS NEVER WRONG.** QA reported
// *"accounts that were not selected still appear"*. They are right about what
// they saw: `GET /cycles/coverage` asks `derivation.covered_unit_ids`, which
// walks EVERY active route on EVERY non-draft cycle, so this tab answers
// *"accounts that reach no cycle at all"* — BR-MET-080's own question, and the
// tenant's whole exposure rather than this cycle's business. Measured on the
// demo utility: `CY-007` (5 routes, 28 accounts) and `CY-001` (0 routes, 0
// accounts) drew the **same 26 rows**.
//
// ⚠ **SO THE CHECK IS THE COMPARISON, NOT THE COUNT.** A row count on one
// cycle cannot tell a utility-wide list from a cycle-scoped one — it reads as
// a perfectly ordinary table either way, which is exactly how this survived
// every suite. Two cycles with different route sets are opened and their row
// sets are compared; identical sets PROVE the scope, and the screen must then
// say so in words.
head("QA 9 — SET-07D Coverage: the list is utility-wide and STATES it (DEF-MET-5854)");

/** Every `/cycles/coverage` answer the page takes, keyed in arrival order. */
const coverageBodies = [];
page.on("response", async (r) => {
  if (r.url().includes("/cycles/coverage")) {
    try { coverageBodies.push(await r.json()); } catch { /* not json — the check below says so */ }
  }
});

/** The cycles on this tenant, newest API answer first — never a hardcoded id. */
const cyclesResp = await page.request.get(`${BASE}/api/${TENANT}/cycles?per=100`);
const cyclesJson = await cyclesResp.json();
const cycles = (cyclesJson.results ?? cyclesJson.rows ?? cyclesJson ?? []).filter(Boolean);
console.log(`      the tenant has ${cycles.length} cycle(s)`);

/** Open one cycle's Coverage tab and read what a clerk reads. */
async function coverageOf(cycle) {
  const before = coverageBodies.length;
  await page.goto(
    `${BASE}/${TENANT}/settings/reference-data/routes-cycles/cycles/${cycle.id}?tab=coverage`,
    { waitUntil: "domcontentloaded" },
  );
  await settle(3000);
  const accounts = await page.locator('tr[data-rc="uncovered"] td:first-child').allTextContents();
  const served = coverageBodies.slice(before).at(-1) ?? null;
  return { accounts: accounts.map((a) => a.trim()), served };
}

// Two cycles that differ as much as this tenant allows: most routes vs fewest.
const byRoutes = [...cycles].sort((a, b) => (b.routes?.length ?? 0) - (a.routes?.length ?? 0));
const rich = byRoutes[0];
const bare = byRoutes.at(-1);
if (rich !== undefined && bare !== undefined && rich.id !== bare.id) {
  const A = await coverageOf(rich);
  await shot("qa9-coverage-rich");
  const B = await coverageOf(bare);
  await shot("qa9-coverage-bare");
  console.log(`      ${rich.code} (${rich.routes?.length ?? 0} route(s)) lists ${A.accounts.length} account(s)`);
  console.log(`      ${bare.code} (${bare.routes?.length ?? 0} route(s)) lists ${B.accounts.length} account(s)`);
  const same = A.accounts.length === B.accounts.length
    && A.accounts.every((x, i) => x === B.accounts[i]);
  if (same) {
    ok(`both cycles list the IDENTICAL ${A.accounts.length} accounts — the list is utility-wide, as designed (D13/BR-MET-080)`);
  } else {
    fail(`the two cycles list DIFFERENT accounts (${A.accounts.length} vs ${B.accounts.length}) — this tab was never per-cycle; something changed its scope`);
  }
  // …and the KPI must read the SERVED count, never the rows on the page.
  if (B.served !== null) {
    const kpi = (await page.locator("text=/Accounts on no cycle/i").first()
      .locator("xpath=..").textContent().catch(() => "")) ?? "";
    console.log(`      the KPI tile reads: "${kpi.replace(/\s+/g, " ").trim()}"`);
    if (kpi.includes(String(B.served.uncovered_accounts))) {
      ok(`the KPI is the SERVED total (${B.served.uncovered_accounts}), not the rows on screen`);
    } else {
      fail(`the KPI does not carry the served total ${B.served.uncovered_accounts}`);
    }
  }
} else {
  fail("fewer than two cycles on this tenant — QA 9's comparison cannot be made here");
}

// ⚠ **THE FIX IS A SENTENCE, SO THE CHECK IS FOR A SENTENCE.** Nothing in this
// repo can see a MISSING one: `tsc`, eslint, 27 vitest cases and every gate
// pass over a table with no heading at all.
const scopeTitle = await page.locator("text=/On no cycle/i").count();
const scopeLine = await page.locator("text=/The whole utility, not this cycle/i").count();
if (scopeTitle > 0) { ok('the uncovered table carries a heading ("On no cycle")'); }
else { fail("the uncovered table still has NO heading — a clerk reads it as this cycle's accounts"); }
if (scopeLine > 0) { ok('…and states its scope: "The whole utility, not this cycle. Put them on a route."'); }
else { fail("the list never says it is utility-wide — this is the reported defect"); }

// B14 rule 33 — the 37-word rationale paragraph is GONE, not shortened.
const oldProse = await page.locator("text=/worked out when the bill run happens/i").count();
if (oldProse === 0) { ok("the old 37-word rationale paragraph is gone (rule 33: rationale is zero words on screen)"); }
else { fail("the rationale paragraph is still drawn beside the new heading — the copy was added, not replaced"); }

// D13 must still hold: no assignment action anywhere on this tab.
const assignAction = await page.locator("text=/Assign a cycle/i").count();
if (assignAction === 0) { ok("still NO `Assign a cycle →` anywhere (D13 intact)"); }
else { fail("an assign-a-cycle action appeared on the Coverage tab — D13 broken"); }

// ═══════════════════════════════════════════════════════════════════════════
// QA 10 · Route detail → the `No meter · verify` badge, against the REGISTRY
// ═══════════════════════════════════════════════════════════════════════════
//
// ⚠ **THE BADGE IS PER BUILDING, NOT PER UNIT, WHICH IS THE FIRST THING TO
// SETTLE.** QA reported *"some units show as having no assets"*; the screen
// draws one badge per STOP, and a stop is a premises (D11 — *"One building,
// one number, however many units are inside it"*). A stop is badged when NO
// unit inside it holds a meter.
//
// ⚠ **LAW 7 — WHAT WOULD MAKE THIS PASS WRONGLY?** *"Some stops show meters"*
// passes while other stops are wrong, so this does not sample: it walks EVERY
// stop of EVERY route and prints the screen's answer beside the Assets
// registry's own answer for that same address (`GET /assets?f.premises_id=`),
// badged and unbadged alike. A disagreement in EITHER direction is named.
head("QA 10 — SET-06D: every stop's badge against the Assets registry (DEF-MET-5856)");

const routesResp = await page.request.get(`${BASE}/api/${TENANT}/routes?per=200`);
const routesJson = await routesResp.json();
const allRoutes = (routesJson.results ?? routesJson.rows ?? routesJson ?? []).filter(Boolean);
console.log(`      walking ${allRoutes.length} route(s)`);

let stopsSeen = 0;
let badgedSeen = 0;
let disagreements = 0;
for (const route of allRoutes) {
  await page.goto(
    `${BASE}/${TENANT}/settings/reference-data/routes-cycles/routes/${route.id}?tab=premises`,
    { waitUntil: "domcontentloaded" },
  );
  await settle(2600);
  // The stop list draws the premise NUMBER, never the id (B14 rule 31), so the
  // id comes from the payload the page itself was served.
  const detail = await (await page.request.get(`${BASE}/api/${TENANT}/routes/${route.id}`)).json();
  // ⚠ **`premises_order` ALONE IS THE WRONG QUESTION, AND THIS CHECK ASKED IT
  // FIRST (caught on its own first run, 2026-09-19).** `stopsFromServedOrder`
  // falls back to `premisesStops(membership)` for a route nobody has
  // SEQUENCED, so three routes drew a stop each over an empty `premises_order`
  // and this reported *"the page draws 1 stop and the payload carries 0"* —
  // a true statement about the wrong field, over a screen that was correct.
  // The fallback is mirrored here rather than restated: the stop list is the
  // served order when there is one, and the distinct premises of the
  // membership, in membership order, when there is not.
  const served = detail.premises_order ?? [];
  const order = served.length > 0
    ? [...served].sort((a, b) => a.walk_order - b.walk_order)
    : (detail.membership ?? []).reduce((acc, m) => {
        if (!acc.some((s) => s.premises_id === m.premises_id)) {
          acc.push({ premises_id: m.premises_id, premise_no: m.premise_no });
        }
        return acc;
      }, []);
  const drawn = await page.locator('[data-rc="stop"]').allInnerTexts();
  if (drawn.length !== order.length) {
    fail(`${route.code}: the page draws ${drawn.length} stop(s) and the route's own payload resolves ${order.length}`);
  }
  for (let i = 0; i < Math.min(drawn.length, order.length); i += 1) {
    stopsSeen += 1;
    const badged = /No meter/.test(drawn[i]);
    if (badged) { badgedSeen += 1; }
    const reg = await (await page.request.get(
      `${BASE}/api/${TENANT}/assets?f.premises_id=${order[i].premises_id}&per=1`,
    )).json();
    const held = Number(reg.count ?? (reg.results ?? []).length ?? 0);
    const agree = badged === (held === 0);
    if (!agree) {
      disagreements += 1;
      fail(`${route.code} stop ${i + 1} (${order[i].premise_no}): the screen says `
        + `${badged ? "NO meter" : "has meters"} and the registry holds ${held} asset(s) at that address`);
    }
    if (badged || i < 2) {
      console.log(`      ${route.code} stop ${String(i + 1).padStart(2)} ${order[i].premise_no}: `
        + `screen=${badged ? "NO METER" : "has meters"}  registry=${held} asset(s)  ${agree ? "agree" : "DISAGREE"}`);
    }
  }
}
console.log(`      ${stopsSeen} stop(s) walked, ${badgedSeen} badged, ${disagreements} disagreement(s)`);
if (disagreements === 0) {
  ok(`every one of ${stopsSeen} stops agrees with the Assets registry — on THIS tenant the screen tells the truth`);
} else {
  fail(`${disagreements} stop(s) disagree with the registry — QA 10 reproduces here`);
}

// ⚠ **AND AGREEING HERE DOES NOT MAKE THE RULE RIGHT, WHICH IS THE FINDING.**
// Both sides of the comparison above ask `AssetAssignment.to_date IS NULL`, so
// they cannot disagree about a DATE. The money path asks a different question
// on the same rows — `from_date <= today AND (to_date IS NULL OR to_date >=
// today) AND the asset is in service` (`assets.billable_asset_count`) — and a
// meter scheduled for removal next month is STILL ON THE UNIT TODAY. Proved by
// construction inside a rolled-back transaction on 2026-09-19: one unit, two
// meters, `to_date` set a month out → `assets_on_unit` answered **0 assets**
// and the stop gained the badge, while the money path's own predicates
// answered **2 assets on the unit today**. That is `DEF-MET-5856`, it is
// QA 10's exact direction, and it is LATENT on this tenant (0 assignments
// carry a future date), so no browser check here can see it.

// ═══════════════════════════════════════════════════════════════════════════
// #3 · S14 premises head — the DRAWN subtitle, and where the counts went
// ═══════════════════════════════════════════════════════════════════════════
//
// The blueprint (*Premises & Units Blueprint 2*, page 6, read AS AN IMAGE per
// B14 rule 42) draws `PREMISES & UNITS` / `Premises` / one subtitle, and
// `CR-089-p005-property-list.md` says it twice: §Header *"No roll-up sentence
// is drawn"*, §Tiles *"None. The screen draws no stat tiles and no KPI strip."*
// B14 rule 41 makes the drawing the specification.
//
// ⚠ **THE SECOND HALF IS THE ONE WORTH CHECKING: NOTHING A CLERK COULD SEE HAS
// BECOME UNREACHABLE.** The drawing's own answer for counts is the chip and
// the footer — *"the chip reads `Not placed ×` and the count in the footer is
// the size of the job"* — so this walks each figure to its new home and prints
// the number it finds there.
head("#3 — S14 head: the drawn subtitle replaces the roll-up (DEF-MET-5855)");
await page.goto(`${BASE}/${TENANT}/premises`, { waitUntil: "domcontentloaded" });
await settle(2800);
await shot("def3-premises-head");

const headText = (await page.locator("h1").first().locator("xpath=..").innerText()).trim();
console.log(`      the head now reads:\n        ${headText.split("\n").join("\n        ")}`);
if (/Every property that takes service, and the units inside them\./.test(headText)) {
  ok("the line under the title is the blueprint's own subtitle");
} else {
  fail("the drawn subtitle is not under the title");
}
if (!/pending activation/.test(headText)) {
  ok("the roll-up sentence is gone from the Premises tab");
} else {
  fail(`the roll-up is still drawn: "${headText}"`);
}

/** `1–50 of 90` → 90. The drawing's own home for a count. */
async function footerTotal() {
  const txt = (await page.locator("text=/of [0-9,]+/").first().textContent().catch(() => "")) ?? "";
  return Number((txt.match(/of\s+([0-9][0-9,]*)/)?.[1] ?? "-1").replace(/,/g, ""));
}
const premisesTotal = await footerTotal();
console.log(`      PREMISES total, in the footer where the drawing puts it: ${premisesTotal}`);
if (premisesTotal > 0) { ok(`the first roll-up figure is the footer's own total (${premisesTotal})`); }
else { fail("the footer carries no total"); }

// `4 pending activation` → the Status chip, then the footer.
await page.goto(`${BASE}/${TENANT}/premises?f.status=pending`, { waitUntil: "domcontentloaded" });
await settle(2600);
const pendingTotal = await footerTotal();
console.log(`      Status = Pending → footer reads ${pendingTotal} (the roll-up's "pending activation")`);
if (pendingTotal >= 0) { ok(`"pending activation" survives as a filter + footer: ${pendingTotal}`); }
else { fail("filtering to Pending produced no count"); }

// `N units` and `N vacant` are UNITS facts and live on the Units tab.
await page.goto(`${BASE}/${TENANT}/premises/units`, { waitUntil: "domcontentloaded" });
await settle(2800);
const unitsTotal = await footerTotal();
await page.goto(`${BASE}/${TENANT}/premises/units?f.occupancy=vacant`, { waitUntil: "domcontentloaded" });
await settle(2800);
const vacantTotal = await footerTotal();
console.log(`      Units tab → footer ${unitsTotal} units; Occupancy = Vacant → footer ${vacantTotal}`);
if (unitsTotal > 0 && vacantTotal >= 0 && vacantTotal <= unitsTotal) {
  ok(`"N units" and "N vacant" survive on the Units tab: ${unitsTotal} and ${vacantTotal}`);
} else {
  fail(`the units figures did not resolve (${unitsTotal} / ${vacantTotal})`);
}

// ⚠ **THE ONE FIGURE WITH NO NEW HOME IS NAMED RATHER THAN GLOSSED.** The
// `+ N common` split has no chip: the units list offers Occupancy, Plan,
// Premise and Service and no common-area filter, so that number is reachable
// only on the Imports tab, where the roll-up still draws because no blueprint
// plate covers it. Filed as `OQ-MET-12484` rather than half-built here.
// ⚠ **STATED, NOT COUNTED.** A first draft printed a control count here off a
// selector that answers `0` on this toolbar — a number that reads as a finding
// and is an artefact of the probe, which is the shape this whole file exists
// to avoid. The four groups are declared in `UnitsListPage.tsx`'s `filters`
// array (Occupancy · Plan · Premise · Service) and a reader can check them
// there.
console.log('      (the units list has no common-area filter, so the "+ N common" split has no chip — OQ-MET-12484)');

// ── verdict ────────────────────────────────────────────────────────────────
head(`RESULT — ${problems.length} problem(s)`);
for (const p of problems) console.log("  ✗ " + p);
console.log(`\nscreenshots in ${SHOTS}`);
await browser.close();
process.exit(problems.length === 0 ? 0 : 1);
