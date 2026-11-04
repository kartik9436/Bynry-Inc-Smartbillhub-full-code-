// ── Trace ──────────────────────────────────────────────
// Change:  PO ruling 2026-09-17, verbatim: *"utility can get their own account
//          types"* — BR-CUS-1079, superseding BR-CUS-094's PLATFORM posture.
// Defects: DEF-CUS-5647 (Add · Edit · Deactivate · Delete drawn over a server
//          that refused all four) · DEF-CUS-5648 (the refusal's message key
//          existed in the backend and in NO catalogue, so the clerk got no
//          sentence at all).
// Screen:  S8 Settings → Reference data → Account types
//          (/{tenant}/settings/reference-data?list=account_types)
// ───────────────────────────────────────────────────────
//
// ⚠ **THIS IS THE ONLY THING THAT PROVES THE FIX** (hard-won law 6). No gate in
// this repository reads rendered output, and the whole of the PO's report is
// about what a rendered button does when it is pressed — `tsc`, 15 backend
// cases and every gate were green over four controls that did nothing.
//
// **WHAT IT WALKS, IN THE ORDER THE PO WOULD:**
//   1. open the card and count the rows the utility starts with (8);
//   2. ADD one, and see it appear in the list;
//   3. USE it — read it back off the account-type picker a clerk actually
//      chooses from, because a row that exists and is never offered is the
//      same defect one table over;
//   4. EDIT its name;
//   5. SWITCH ONE OFF, and see the list say so;
//   6. TRY TO DELETE A USED ONE and a built-in one, and READ THE SENTENCE —
//      `DEF-CUS-5648` is entirely about there being no sentence.
//
// ⚠ **IT SCREENSHOTS EACH STEP.** A walkthrough that prints "ok" is a check
// whose output cannot distinguish pass from fail to a reader (law 7 habit 3).
//
// ── HOW TO RUN IT ───────────────────────────────────────────────────────────
//   (cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \
//      DATABASE_URL=postgres://sbh:sbh@127.0.0.1:5432/sbh \
//      JOBS_EAGER=false .venv/bin/python manage.py runserver 127.0.0.1:8110 --noreload)
//   (cd 07-frontend && npx vite build && PORT=8131 \
//      API_PROXY_TARGET=http://127.0.0.1:8110 node server.mjs)
//   node 10-scripts/po_20260917_account_types_walkthrough.mjs
const { existsSync, readdirSync, mkdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8131";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const SHOTS = process.env.SHOTS ?? "/tmp/account-types-walk";
const NEW_CODE = process.env.NEW_CODE ?? "marina_berth";
const WIDTH = Number(process.env.WIDTH ?? 1440);
//: The isolation half. Unset means step 8 is SKIPPED and says so — a skipped
//: step that printed nothing would read exactly like a passed one (law 7).
const SECOND_TENANT = process.env.SECOND_TENANT ?? "";
const SECOND_EMAIL = process.env.SECOND_EMAIL ?? "";
const SECOND_PASSWORD = process.env.SECOND_PASSWORD ?? PASSWORD;

mkdirSync(SHOTS, { recursive: true });

/** The pinned revision is usually absent in this container; any chromium beats
 *  not running at all, and the substitution is printed so nobody is surprised. */
function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of [
        "chrome-linux64/chrome",
        "chrome-linux/chrome",
        "chrome-linux/headless_shell",
      ]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) {
          console.log(`chromium: pinned revision missing; using ${candidate}`);
          return candidate;
        }
      }
    }
  }
  throw new Error("no chromium found — run `npx playwright install chromium` from 07-frontend");
}

/** ⚠ **THE BUNDLE IS SHARED AND A SIBLING LANE REBUILDS IT UNDER YOU.** A
 *  `vite build` empties `07-frontend/dist` for about a minute, and every page
 *  served in that window is the server's own *"no index.html … was the bundle
 *  built?"* — which renders as a SKELETON and reads exactly like a product
 *  fault on whatever tenant you happened to be walking. It cost twenty minutes
 *  of diagnosing a tenant that was fine, so the walk now says so out loud
 *  rather than reporting a finding it does not have. */
async function refuseIfBundleIsMissing(p) {
  const body = (await p.textContent("body")) ?? "";
  if (body.includes("no index.html")) {
    throw new Error(
      "the frontend bundle is not built (a sibling lane is probably running " +
        "`vite build`). Re-run when `07-frontend/dist/index.html` exists — this " +
        "is NOT a finding about the product.",
    );
  }
}

const failures = [];
function fail(message) {
  failures.push(message);
  console.log(`  ✗ ${message}`);
}
function ok(message) {
  console.log(`  ✓ ${message}`);
}

let step = 0;
async function shot(page, name) {
  step += 1;
  const file = join(SHOTS, `${String(step).padStart(2, "0")}-${name}.png`);
  await page.screenshot({ path: file, fullPage: true });
  console.log(`    → ${file}`);
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: WIDTH, height: 1100 } });

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL(`**/${TENANT}/dashboard`, { timeout: 20000 });

const CARD = `${BASE}/${TENANT}/settings/reference-data?list=account_types`;

/** Every code the table is currently showing, read off the rendered rows. */
async function codesOnScreen() {
  await page.waitForSelector("table tbody tr", { timeout: 15000 });
  return page.$$eval("table tbody tr", (rows) =>
    rows.map((tr) => (tr.querySelector("td")?.textContent ?? "").trim()).filter(Boolean),
  );
}

/** One tenant's whole list, read through the API this session is signed in to. */
async function codesForTenant(tenantSub) {
  return page.evaluate(async (tenant) => {
    const body = await (
      await fetch(`/api/${tenant}/lookups/account_types?per=200`, {
        headers: { Accept: "application/json" },
      })
    ).json();
    return (body.results ?? []).map((r) => r.code);
  }, tenantSub);
}

/** The whole row, as text, for one code. */
async function rowText(code) {
  return page.$$eval(
    "table tbody tr",
    (rows, wanted) => {
      const hit = rows.find(
        (tr) => (tr.querySelector("td")?.textContent ?? "").trim() === wanted,
      );
      return hit ? (hit.textContent ?? "").replace(/\s+/g, " ").trim() : null;
    },
    code,
  );
}

/** ⚠ **A WALKTHROUGH THAT CANNOT BE RUN TWICE IS A WALKTHROUGH NOBODY RUNS
 *  AGAIN.** The first draft left its own row and its own deactivation behind, so
 *  the second run opened on nine rows and found `Reactivate` where it expected
 *  `Deactivate` — a harness fault that reads exactly like a product one. This
 *  puts the tenant back the way it found it, through the product's own doors. */
async function resetTenant(tenantSub) {
  await page.goto(`${BASE}/${tenantSub}/settings/reference-data?list=account_types`, {
    waitUntil: "networkidle",
  });
  await refuseIfBundleIsMissing(page);
  await page.waitForSelector("table tbody tr", { timeout: 15000 });
  const removed = await page.evaluate(
    async ([tenant, code]) => {
      const list = await (
        await fetch(`/api/${tenant}/lookups/account_types?per=200`, {
          headers: { Accept: "application/json" },
        })
      ).json();
      const out = [];
      for (const row of list.results ?? []) {
        if (row.code === code) {
          await fetch(`/api/${tenant}/lookups/account_types/${row.id}`, { method: "DELETE" });
          out.push(`deleted ${row.code}`);
        } else if (!row.active) {
          await fetch(`/api/${tenant}/lookups/account_types/${row.id}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ active: true }),
          });
          out.push(`reactivated ${row.code}`);
        }
      }
      return out;
    },
    [tenantSub, NEW_CODE],
  );
  if (removed.length) console.log(`    (reset: ${removed.join(", ")})`);
}

// ── 1 · the list the utility starts with ────────────────────────────────────
console.log(`\n1 · the card opens — ${CARD}`);
await resetTenant(TENANT);
await page.goto(CARD, { waitUntil: "networkidle" });
await refuseIfBundleIsMissing(page);
const before = await codesOnScreen();
console.log(`    ${before.length} row(s): ${before.join(" · ")}`);
await shot(page, "card-as-found");
if (before.length < 8) {
  fail(`only ${before.length} rows — BR-CUS-094's seven plus government is EIGHT`);
} else {
  ok(`${before.length} rows, the utility's own`);
}

// ── 2 · ADD — the control the PO reported as doing nothing ──────────────────
console.log(`\n2 · Add "${NEW_CODE}"`);
await page.getByRole("button", { name: /Add entry/ }).first().click();
const modal = page.locator('[role="dialog"]').first();
await modal.waitFor({ timeout: 10000 });
await modal.locator("input").first().fill(NEW_CODE);
await modal.locator("input").nth(1).fill("Marina berth");
await shot(page, "add-dialog");
await modal.getByRole("button", { name: /^(Save|Add)/ }).last().click();
await page.waitForTimeout(1500);
const after = await codesOnScreen();
await shot(page, "added");
if (after.includes(NEW_CODE)) {
  ok(`the row is on screen — ${after.length} rows now`);
} else {
  fail(`Add did nothing: the list is still ${after.join(" · ")} (DEF-CUS-5647)`);
}

// ── 3 · USE IT — the picker a clerk actually chooses from ───────────────────
// A row that exists and is never OFFERED is the same defect one table over,
// and it is exactly what `GET /service-requests/categories` did: it iterated
// the seven ratified codes over the live rows, so a tenant's own row could not
// appear however active it was.
console.log("\n3 · the row is OFFERED, not merely stored");
const offered = await page.evaluate(async (tenant) => {
  const res = await fetch(`/api/${tenant}/service-requests/categories`, {
    headers: { Accept: "application/json" },
  });
  const body = await res.json();
  return {
    selectable: (body.selectable ?? []).map((r) => r.code),
    legacy: (body.legacy ?? []).map((r) => r.code),
  };
}, TENANT);
console.log(`    selectable: ${offered.selectable.join(" · ")}`);
console.log(`    legacy:     ${offered.legacy.join(" · ") || "(none)"}`);
if (offered.selectable.includes(NEW_CODE)) {
  ok("the picker offers the tenant's own row");
} else {
  fail(`the picker dropped ${NEW_CODE} — it is reading a tuple, not the rows (DEF-CUS-5647)`);
}
if (offered.selectable[0] !== "residential") {
  fail(`the picker re-ordered the drawn screen: it starts at ${offered.selectable[0]}`);
} else if (offered.selectable[offered.selectable.length - 1] !== NEW_CODE) {
  fail("a tenant-added row must land AFTER the ruled seven, not among them");
} else {
  ok("the ruled order survives and the new row is appended");
}

// ── 4 · EDIT ────────────────────────────────────────────────────────────────
console.log("\n4 · rename it");
await page.goto(CARD, { waitUntil: "networkidle" });
await refuseIfBundleIsMissing(page);
await page.waitForSelector("table tbody tr", { timeout: 15000 });
const newRow = page.locator("table tbody tr", { hasText: NEW_CODE }).first();
await newRow.waitFor({ timeout: 15000 });
await newRow.getByRole("button", { name: /^Edit$/ }).click();
const editModal = page.locator('[role="dialog"]').first();
await editModal.waitFor({ timeout: 10000 });
await editModal.locator("input").nth(1).fill("Boat slip");
await editModal.getByRole("button", { name: /^Save/ }).last().click();
await page.waitForTimeout(1500);
await shot(page, "renamed");
const renamed = await rowText(NEW_CODE);
if (renamed && renamed.includes("Boat slip")) ok("the name changed");
else fail(`Edit did not take: ${renamed}`);

// ── 5 · DEACTIVATE ──────────────────────────────────────────────────────────
console.log("\n5 · switch a built-in one off");
await page.goto(CARD, { waitUntil: "networkidle" });
await page.waitForSelector("table tbody tr", { timeout: 15000 });
const industrial = page.locator("table tbody tr", { hasText: "industrial" }).first();
await industrial.waitFor({ timeout: 15000 });
await industrial.getByRole("button", { name: /^Deactivate$/ }).click();
await page.waitForTimeout(1500);
await shot(page, "deactivated");
const industrialRow = await rowText("industrial");
console.log(`    industrial: ${industrialRow}`);
const stillOffered = await page.evaluate(async (tenant) => {
  const res = await fetch(`/api/${tenant}/service-requests/categories`, {
    headers: { Accept: "application/json" },
  });
  return ((await res.json()).selectable ?? []).map((r) => r.code);
}, TENANT);
if (stillOffered.includes("industrial")) {
  fail("a switched-off type is still offered on the picker (BR-TEN-034)");
} else {
  ok("switched off, and the picker stops offering it");
}

// ── 6 · DELETE — and READ THE SENTENCE ──────────────────────────────────────
// `DEF-CUS-5648` is entirely about a refusal with no words on it, so this step
// FAILS on an empty reason even when the button is correctly locked.
console.log("\n6 · try to delete a built-in one, and a used one");
await page.goto(CARD, { waitUntil: "networkidle" });
await page.waitForSelector("table tbody tr", { timeout: 15000 });
for (const code of ["residential", "commercial"]) {
  const row = page.locator("table tbody tr", { hasText: code }).first();
  const locked = row.getByRole("button", { name: /Delete/ }).first();
  const reason =
    (await locked.getAttribute("title")) ?? (await locked.getAttribute("aria-label")) ?? "";
  const disabled = await locked.isDisabled();
  console.log(`    ${code}: delete ${disabled ? "LOCKED" : "live"} — "${reason}"`);
  if (!disabled) {
    fail(`${code} is seeded and/or in use and Delete is live (BR-TEN-034/036)`);
  } else if (reason.trim() === "") {
    fail(`${code}'s Delete is locked with NO REASON on it — that is DEF-CUS-5648 again`);
  } else {
    ok(`${code} is locked, in words`);
  }
}
await shot(page, "delete-locks");

// …and the one the tenant added, which is genuinely deletable.
console.log(`\n   …and ${NEW_CODE}, which nothing uses`);
const mine = page.locator("table tbody tr", { hasText: NEW_CODE }).first();
const del = mine.getByRole("button", { name: /Delete/ }).first();
if (await del.isDisabled()) {
  fail(`${NEW_CODE} is the tenant's own and unused — Delete must be live`);
} else {
  await del.click();
  // ⚠ `ConfirmDialog` is `role="alertdialog"`, not `role="dialog"` — a
  // consequence before an irreversible act is a different kind of thing from an
  // editor, and the walkthrough has to look for the one the product renders.
  const confirm = page.locator('[role="alertdialog"]').first();
  await confirm.waitFor({ timeout: 10000 });
  await shot(page, "delete-confirm");
  await confirm.getByRole("button", { name: /Delete/ }).last().click();
  await page.waitForTimeout(1500);
  const left = await codesOnScreen();
  await shot(page, "deleted");
  if (left.includes(NEW_CODE)) fail("Delete did nothing");
  else ok(`deleted — ${left.length} rows left`);
}

// ══════════════════════════════════════════════════════════════════════════
// 7 · THE NEIGHBOURS — the screens that CHOOSE and SHOW a category
// ══════════════════════════════════════════════════════════════════════════
// ⚠ **THIS IS THE PO'S ACTUAL REPORT, WORD FOR WORD:** *"if they add entry in
// this table - look up it does not reflect in these places"*. The card is half
// the walk; the other half is the screen where a clerk PICKS one. The New
// Account wizard's step-1 category control reads `useAccountCategories()` →
// `GET /service-requests/categories`, which is the endpoint that iterated a
// seven-code tuple and dropped a tenant's own row (`DEF-CUS-5647`).
console.log("\n7 · the added type reaches the screens that USE it");
await page.goto(CARD, { waitUntil: "networkidle" });
await page.getByRole("button", { name: /Add entry/ }).first().click();
{
  const m = page.locator('[role="dialog"]').first();
  await m.waitFor({ timeout: 10000 });
  await m.locator("input").first().fill(NEW_CODE);
  await m.locator("input").nth(1).fill("Marina berth");
  await m.getByRole("button", { name: /^(Save|Add)/ }).last().click();
  await page.waitForTimeout(1500);
}

await page.goto(`${BASE}/${TENANT}/accounts/new`, { waitUntil: "networkidle" });
await page.waitForTimeout(2500);
await shot(page, "new-account-wizard");
const wizardText = (await page.textContent("body")) ?? "";
if (wizardText.includes("Marina berth")) {
  ok("the New Account wizard offers it as a customer category");
} else if (/not built|coming|Sign in/i.test(wizardText)) {
  console.log("    (the wizard did not open on this build — reporting, not asserting)");
} else {
  fail(
    "the New Account wizard does not offer the tenant's own category — " +
      "this is DEF-CUS-5647's shape on the screen the PO reported",
  );
}

// ══════════════════════════════════════════════════════════════════════════
// 8 · TWO UTILITIES, ONE CODE, AND NEITHER SEES THE OTHER'S
// ══════════════════════════════════════════════════════════════════════════
// ⚠ **THIS IS THE WHOLE POINT OF THE CHANGE AND THE THING RLS MUST ENFORCE.**
// A passing unit test is weaker evidence than two signed-in sessions, because
// the test runs on sqlite where the policy does not exist at all.
if (SECOND_TENANT) {
  console.log(`\n8 · ${TENANT} and ${SECOND_TENANT} both add "${NEW_CODE}"`);
  const first = await codesForTenant(TENANT);
  console.log(`    ${TENANT}: ${first.length} rows`);

  await page.goto(`${BASE}/${SECOND_TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", SECOND_EMAIL);
  await page.fill("#signin-password", SECOND_PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(`**/${SECOND_TENANT}/dashboard`, { timeout: 20000 });
  await resetTenant(SECOND_TENANT);

  await page.goto(`${BASE}/${SECOND_TENANT}/settings/reference-data?list=account_types`, {
    waitUntil: "networkidle",
  });
  const secondBefore = await codesOnScreen();
  console.log(`    ${SECOND_TENANT}: ${secondBefore.length} rows — ${secondBefore.join(" · ")}`);
  if (secondBefore.includes(NEW_CODE)) {
    fail(
      `${SECOND_TENANT} can see ${TENANT}'s own category. That is the platform ` +
        "table wearing a tenant column, and it is the whole thing RLS is for",
    );
  } else {
    ok(`${SECOND_TENANT} cannot see ${TENANT}'s addition`);
  }

  // …and the SAME code is accepted here, which the old global unique refused.
  await page.getByRole("button", { name: /Add entry/ }).first().click();
  const m2 = page.locator('[role="dialog"]').first();
  await m2.waitFor({ timeout: 10000 });
  await m2.locator("input").first().fill(NEW_CODE);
  await m2.locator("input").nth(1).fill("Boat slip");
  await m2.getByRole("button", { name: /^(Save|Add)/ }).last().click();
  await page.waitForTimeout(1500);
  await shot(page, "second-tenant-same-code");
  const secondAfter = await rowText(NEW_CODE);
  if (secondAfter && secondAfter.includes("Boat slip")) {
    ok(`${SECOND_TENANT} holds the SAME code with its OWN name — "Boat slip"`);
  } else {
    fail(
      `${SECOND_TENANT} could not take the code ${TENANT} already uses: ${secondAfter}. ` +
        "The unique constraint is still global",
    );
  }

  // Back to the first utility: its own row must be untouched.
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(`**/${TENANT}/dashboard`, { timeout: 20000 });
  await page.goto(CARD, { waitUntil: "networkidle" });
  const mine = await rowText(NEW_CODE);
  console.log(`    back on ${TENANT}: ${mine}`);
  await shot(page, "first-tenant-unchanged");
  if (mine && mine.includes("Marina berth")) {
    ok(`${TENANT}'s own name survived the other utility's write`);
  } else {
    fail(`${TENANT}'s row changed under it: ${mine}`);
  }
  await resetTenant(TENANT);
} else {
  console.log("\n8 · SECOND_TENANT not set — the two-tenant walk was SKIPPED, not passed");
}

await browser.close();
console.log(failures.length === 0 ? "\nOK" : `\n${failures.length} finding(s)`);
process.exit(failures.length === 0 ? 0 : 1);
