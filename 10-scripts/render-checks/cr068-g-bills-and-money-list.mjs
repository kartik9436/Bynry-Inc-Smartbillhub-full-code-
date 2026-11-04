/**
 * RENDERED-OUTPUT CHECK — CR-068 wave G, "Bills, documents and the money list",
 * in a real browser.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: no gate in this repository looks at
 * rendered output, and nine defects in one day were found this way and by
 * nothing else. PO ruling 2026-09-03: *"ensure you do web walkthorugh before
 * you sign off the user story or build"*. `10-execution-plan.md` names this
 * file at wave G task **G4** and it did not exist until 2026-09-06.
 *
 * ⚠ **AND THIS WAVE TOUCHES MONEY, WHICH CHANGES WHAT AN ASSERTION IS WORTH.**
 * Every figure here is DISPLAYED money: stored to four decimals, drawn to two
 * (hard rule 2). So the checks below read the SCREEN's strings and do the
 * arithmetic on them — `charges + tax = total` out of three rendered cells,
 * which is `US-CWP-033` TC-2's own acceptance — rather than trusting a payload
 * the screen may have rounded on its way past. A figure that disagrees with a
 * signed one is a defect to FILE, never a number to adjust.
 *
 * ── TWO TRAPS THIS FILE IS BUILT AROUND ───────────────────────────────────
 *
 * **1 · ASSERT IN THE STATE THE SCREEN IS NORMALLY IN.** `DEF-WRK-4121` shipped
 * a dispatcher who could not raise a work order on any non-empty list, because
 * every test exercised the EMPTY list — the one state where it worked. So every
 * check here that says something about rows first proves there ARE rows, and
 * says how many out loud.
 *
 * **2 · A CHECK THAT CANNOT FAIL IS WORSE THAN NO CHECK, because it is
 * trusted.** `[].every(...)` is `true`. On a money screen the same trap wears a
 * second face: **a total that matches because both sides are zero has proved
 * nothing.** So the money checks refuse a zero: `expectMoney` fails on `$0.00`
 * unless a zero is the thing being asserted, and the two-column check demands a
 * row where `owing` genuinely DIFFERS from `amount` — on an all-paid list,
 * "owing is its own column" is true of a column of zeroes and means nothing.
 *
 * ⚠ **THE FIXTURE IS THE HALF THAT WAS MISSING, NOT THE SCRIPT.** Wave G task
 * G3 names *"the four bills, the corrected pair, the bounce, the adjustment,
 * the write-off, 41 documents, the intents"* and none of it was written;
 * `seed_portal_demo` plants a generic estate where **every payment is
 * cleared**. `cr068-g-fixture.py` bounces one payment through the real
 * `payments.reversal.reverse_payment` service so step 5 has two rows to look
 * at. It deliberately does NOT manufacture the corrected pair — that path is
 * human-owned money math — so **step 1's `BR-CWP-042` assertions SKIP BY NAME
 * and the run says so**, rather than passing silently over an absence
 * (hard-won law 7: a declared blind spot with no number attached is
 * indistinguishable from an empty one).
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   eval "$(10-scripts/proof-db.sh clone cwpg --export)"
 *   export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false
 *   (cd 06-backend && python3 manage.py migrate && python3 manage.py seed_portal_demo)
 *   (cd 06-backend && python3 manage.py shell < ../10-scripts/render-checks/def-cwp-3965-fixture.py)
 *   (cd 06-backend && python3 manage.py shell < ../10-scripts/render-checks/cr068-g-fixture.py)
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8141 --noreload &
 *   (cd 07-frontend && ./node_modules/.bin/vite build && \
 *      PORT=4341 API_PROXY_TARGET=http://127.0.0.1:8141 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4341 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr068-g-bills-and-money-list.mjs
 *
 * ⚠ **BUILD THE BUNDLE BEFORE YOU DRIVE IT.** A stale `dist/` means every
 * assertion below passes or fails about a build nobody is shipping.
 *
 * ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** A mid-run reseed
 * looks exactly like a broken screen.
 *
 * ⚠ **IT SIGNS IN AS THE LANDLORD, AND THAT IS A CHOICE ABOUT EVIDENCE.**
 * `ana@example.test` holds one account, owes every bill she has been sent and
 * has made NO payments — `GET /portal/payments` answers `{"money":[]}` for her,
 * so `CWP-041` would be exercised in its empty state and steps 5 and 7 would
 * prove nothing. `maria@example.test` holds three accounts, six bills in four
 * different states including a genuinely **part-paid** one, and six payments
 * including the planted bounce. Step 8 opens the empty state deliberately, with
 * the householder, so both states are seen rather than neither.
 *
 * ── WHAT IT CLICKS (the wave G demo script, 10-execution-plan.md) ─────────
 *   1  `CWP-027` Bills — owing is a column of its own and DIFFERS from amount
 *      on at least one row; the status words; the corrected pair (SKIPPED, by
 *      name, when the fixture could not plant one); every quantity cell carries
 *      its unit; filter *Unpaid* keeps the part-paid row.
 *   2  `CWP-028` One bill — the lines, grouped by service, and
 *      `charges + tax = total` computed FROM THE DISPLAYED STRINGS.
 *   3  `CWP-029` The bill as it was printed — the same bytes twice, hashed.
 *   4  `CWP-031` Documents and letters — rows named for what they ARE, the
 *      route each went by, the footer's count.
 *   5  `CWP-041` Payments — the bounce as TWO ROWS, the reversal directly above
 *      the row it undoes, drawn in the danger tier, negative.
 *   6  Every Pay control on all four screens: live door, or disabled WITH a
 *      visible reason of six words or fewer (B14 rule 33).
 *   7  A forced click on a held control writes nothing — no payment row.
 *   8  A customer with no payments gets an empty state that says what fills it,
 *      never a blank table (B14 rule 17).
 *   9  Nothing on any of these screens shows a database id or an internal code
 *      (B14 rule 31 · rule 32).
 */

import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

import { Gaps } from "./lib/knownGaps.mjs";
import { attachTimings } from "./lib/timings.mjs";

const require = createRequire(join(process.cwd(), "07-frontend", "package.json"));
const { chromium } = require("playwright-core");

/**
 * Where chromium actually is.
 *
 * ⚠ **`executablePath()` RETURNS A PATH, NOT A BROWSER, AND A TRY/CATCH AROUND
 * IT CANNOT SEE THE DIFFERENCE.** Playwright computes the path from the version
 * it was built against — on this machine it answers
 * `/opt/pw-browsers/chromium-1234/chrome-linux64/chrome` while what is
 * installed is `chromium-1194/chrome-linux/chrome`. **Nothing throws**, so the
 * `catch` never runs, the fallback glob never runs either, and the launch fails
 * much later with a message about the browser rather than about the lookup.
 * That is hard-won law 7's second shape — a check structurally incapable of
 * failing — so the path is TESTED here rather than trusted.
 *
 * The same eight lines are in `cr068-e-getting-in.mjs` and its four siblings;
 * they work only because their `PLAYWRIGHT_BROWSERS_PATH` happens to agree with
 * the build. Recorded rather than quietly copied.
 */
function resolveChromium() {
  const candidates = [];
  try {
    candidates.push(chromium.executablePath());
  } catch {
    /* the computed path is optional — the glob below is the real answer */
  }
  try {
    candidates.push(
      execFileSync("bash", [
        "-lc",
        "ls -d /opt/pw-browsers/chromium-*/chrome-linux/chrome /opt/pw-browsers/chromium-*/chrome-linux64/chrome 2>/dev/null | head -1",
      ])
        .toString()
        .trim(),
    );
  } catch {
    /* nothing installed under /opt — the error below names what was tried */
  }
  for (const candidate of candidates) {
    if (candidate && existsSync(candidate)) return candidate;
  }
  throw new Error(
    `no chromium executable found. Tried: ${candidates.filter(Boolean).join(", ") || "(nothing)"}`,
  );
}

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4341";
const TENANT = process.env.SMOKE_TENANT ?? "pine-hill";
const LANDLORD_EMAIL = process.env.SMOKE_LANDLORD_EMAIL ?? "maria@example.test";
const HOUSEHOLDER_EMAIL = process.env.SMOKE_HOUSEHOLDER_EMAIL ?? "ana@example.test";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "Pine-Hill-2026!";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr068-g";
const VIEWPORT = { width: 1440, height: 1000 };

const PORTAL = `${BASE}/${TENANT}/portal`;

mkdirSync(OUT, { recursive: true });

const failures = [];
const skipped = [];

/**
 * The gaps this run knowingly does not prove.
 *
 * ⚠ **A GAP IS NOT A SKIP, AND THE DIFFERENCE IS THE HALF THAT MATTERS.** The
 * first draft of this file used `skip()` for both open gaps, which declares an
 * absence honestly and then **never notices when it closes** — the same
 * one-directional promise `holds.ts` exists to stop on the UI side, and the
 * shape `DEF-CWP-3925` cost eight times. `Gaps.known()` fails when the product
 * grows the thing and this file still says it has not, so the register cannot
 * rot. `skip()` is kept for a step that could not RUN (no data to look at at
 * all), which is a different statement from a gap between drawing and product.
 */
const gaps = new Gaps();
/** Every money figure this run READ OFF THE SCREEN, printed at the end. */
const figures = [];

function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

/**
 * A step this run could not exercise, named out loud.
 *
 * ⚠ **THIS IS NOT A PASS AND IS NOT COUNTED AS ONE.** Hard-won law 7's fifth
 * shape is a check reporting zero over a scope it silently excludes — *"a
 * declared blind spot with no NUMBER attached is indistinguishable from an
 * empty one"*. So a skip prints, is counted, and is repeated in the summary.
 */
function skip(message) {
  console.log(`   ⏭ SKIPPED — ${message}`);
  skipped.push(message);
}

/** Displayed money: `$1,234.56`. Two decimals, always (hard rule 2). */
const MONEY = /^-?\$[\d,]+\.\d{2}$/;

/**
 * Assert a rendered money string, and REFUSE A SILENT ZERO.
 *
 * ⚠ **`$0.00` IS THE SHAPE A BROKEN MONEY SCREEN TAKES**, and it satisfies
 * every format check ever written. A total that ties because both sides are
 * zero has proved nothing at all. So a zero has to be asked for explicitly.
 */
function expectMoney(raw, where, { allowZero = false } = {}) {
  const text = (raw ?? "").trim();
  const ok = MONEY.test(text);
  check(ok, `${where}: "${text}" is money drawn to 2 decimals`);
  if (ok && !allowZero) {
    check(
      Number(text.replace(/[$,]/g, "")) !== 0,
      `${where}: …and it is not $0.00 — a zero here would satisfy every other check on this page`,
    );
  }
  if (ok) figures.push(`${where} = ${text}`);
  return ok ? Number(text.replace(/[$,]/g, "")) : Number.NaN;
}

/** B14 rule 31 and rule 32 — never an id, never an internal code, on screen. */
const FORBIDDEN = [
  /\bBR-[A-Z]{3}-\d{3,5}\b/,
  /\bOQ-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /\bDEF-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /\bCWP-\d{3}\b/,
  /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
];

/**
 * Nothing internal on screen — with ONE sanctioned exception, excluded by
 * ELEMENT rather than by weakening the pattern.
 *
 * ⚠ **THE SCREEN-ID CHIP IS A PO-RULED FEATURE, NOT A RULE-31 BREACH.** PO,
 * 2026-09-03: *"We need unique screen ID - on every screen"* (`CR-068` §9). It
 * renders bottom-right behind the `VITE_SCREEN_ID_TAG` switch, is
 * `aria-hidden`, intercepts no click and does not print. The first draft of
 * this walkthrough flagged it on all seven screens — seven false failures over
 * a thing the PO asked for, which is exactly the *check that fails wrongly*
 * this file's header warns about in the other direction.
 *
 * It is removed from the text by its `data-testid` rather than by dropping
 * `CWP-\d{3}` from the list, because the pattern still has work to do: a screen
 * id written into a HEADING or a refusal sentence is a real breach, and
 * loosening the pattern would be the thing that stops it being caught.
 */
async function noInternals(page, where) {
  const text = await page.evaluate(() => {
    const clone = document.body.cloneNode(true);
    clone
      .querySelectorAll('[data-testid="screen-id-tag"]')
      .forEach((node) => node.remove());
    return clone.innerText;
  });
  for (const pattern of FORBIDDEN) {
    check(!pattern.test(text), `${where}: nothing matching ${pattern} on screen (B14 rule 31/32)`);
  }
}

/**
 * Every control on this screen that REFUSES — and whether its refusal is still
 * true.
 *
 * ⚠ **NOTHING IN THIS REPOSITORY ASKS THIS QUESTION** and it has cost eight
 * times. `DEF-CWP-3925`: the portal's front page offered **two working doors
 * out of eight**, every refusal correct on the day it was written and rotted
 * silently when the screens landed. `CR-068` R3 holds a control *until its
 * screen lands*, which is a rule with a clock in it.
 *
 * So this returns what it FOUND rather than asserting a count: the caller
 * prints each held control with its reason and its destination, and a human
 * reading the run can see a hold sitting over a screen that has shipped.
 * Two things ARE asserted mechanically, because they are true of every hold:
 * the reason is VISIBLE (not only a `title`), and it is six words or fewer
 * (B14 rule 33).
 */
async function heldControls(page, where) {
  const held = page.locator('[data-held="true"]');
  const count = await held.count();
  console.log(`   · ${where}: ${count} held control(s)`);
  for (let i = 0; i < count; i += 1) {
    const one = held.nth(i);
    const label = (await one.locator("button").first().innerText().catch(() => "")).trim();
    const reason = (await one.locator("span").last().innerText().catch(() => "")).trim();
    const disabled = await one.locator("button").first().isDisabled().catch(() => false);
    console.log(`     – "${label}" — held: "${reason}"`);
    check(disabled, `${where}: the held control "${label}" is actually disabled, not merely styled`);
    check(
      reason.length > 0,
      `${where}: "${label}" states its reason ON SCREEN, not only in a title attribute`,
    );
    const words = reason.split(/\s+/).filter(Boolean).length;
    check(words <= 6, `${where}: "${label}"'s reason is ${words} words (B14 rule 33 caps it at six)`);
  }
  return count;
}

/**
 * Every account this login holds, walked one at a time.
 *
 * ⚠ **WITHOUT THIS, THE TWO ASSERTIONS THIS WAVE EXISTS FOR ARE BOTH VACUOUS,
 * AND THE FIRST RUN OF THIS FILE PROVED IT.** `/bills` and `/payments` are
 * scoped to the account the SWITCHER is naming, and the landlord's three
 * accounts do not hold the same shapes: the part-paid bill (`BR-CWP-043`'s
 * third state) is on one, the bounced payment (`BR-CWP-061`) is on another, and
 * the account the switcher happens to open on has NEITHER. A run that looked
 * only at the default account reported *"every row owes all or nothing"* and
 * *"no returned payment on this fixture"* — two skips and a failure, over a
 * database that held both.
 *
 * **That is the `DEF-WRK-4121` shape one level up:** not an empty list, but the
 * one slice of a real list where the interesting state is absent. So the walk
 * collects across every account and says which one each finding came from.
 */
async function forEachAccount(page, visit) {
  const select = page.locator('[data-account-switcher="select"]');
  const found = [];
  if ((await select.count()) === 0) {
    // One account → the switcher is a LABEL, not a control (wave E's own rule).
    found.push(await visit("the only account"));
    return found;
  }
  const values = await select.locator("option").evaluateAll((options) =>
    options.map((o) => ({ value: o.value, label: (o.textContent || "").trim() })),
  );
  for (const option of values) {
    await select.selectOption(option.value);
    await page.waitForTimeout(500);
    found.push(await visit(option.label));
  }
  return found;
}

async function signIn(page, email) {
  await page.goto(`${PORTAL}/sign-in`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-015"]', { timeout: 20000 });
  await page.fill("#portal-email", email);
  await page.fill("#portal-password", PASSWORD);
  await page.getByRole("button", { name: /sign in/i }).click();
  await page.waitForSelector('[data-portal-frame="shell"]', { timeout: 20000 });
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const timings = attachTimings(context);
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });
  console.log(`cr068-g: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);
  console.log(`         signed in as ${LANDLORD_EMAIL} (the landlord — see the header)`);

  await signIn(page, LANDLORD_EMAIL);

  // ═════ 1 · CWP-027 — owing is a column, and it is not the amount ═════════
  console.log("\n── 1 · Bills: two money columns, and a third state between them ──");
  await page.goto(`${PORTAL}/bills`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-027"]', { timeout: 20000 });

  // ⚠ **ROWS FIRST.** `DEF-WRK-4121` — every assertion below is about rows, and
  // on an empty table each one is vacuously true. So the row count is proved
  // and PRINTED before anything is claimed about what is in them.
  const billRows = page.locator('[data-screen="CWP-027"] tbody tr');
  const billCount = await billRows.count();
  check(billCount > 0, `the bills table has ${billCount} row(s) — every check below needs rows`);
  if (billCount === 0) {
    skip("everything about CWP-027's rows — the table is empty on this fixture");
  }

  // The two columns, read off the SCREEN and compared to each other.
  const amounts = await page.locator("[data-amount]").allInnerTexts();
  const owings = await page.locator("[data-owing]").allInnerTexts();
  check(
    amounts.length === billCount && owings.length === billCount,
    `every row draws both an amount (${amounts.length}) and an owing (${owings.length})`,
  );
  for (let i = 0; i < amounts.length; i += 1) {
    check(MONEY.test(amounts[i].trim()), `row ${i + 1} amount "${amounts[i].trim()}" is 2-dp money`);
    check(MONEY.test(owings[i].trim()), `row ${i + 1} owing "${owings[i].trim()}" is 2-dp money`);
  }
  console.log(`   · amounts: ${amounts.map((a) => a.trim()).join(" · ")}`);
  console.log(`   · owing:   ${owings.map((o) => o.trim()).join(" · ")}`);

  // ⚠ **THE WHOLE POINT OF `BR-CWP-043`, AND IT NEEDS A ROW WHERE THEY
  // DIFFER.** On an all-paid list every owing is `$0.00` and "owing is its own
  // column" is true of a column of zeroes — a check that cannot fail. So this
  // demands a row where the two figures are genuinely different AND neither is
  // the other's zero.
  // ⚠ **ACROSS EVERY ACCOUNT, NOT JUST THE ONE THE SWITCHER OPENED ON.** See
  // `forEachAccount` — the part-paid bill is on one of the landlord's three
  // accounts and the default is not it.
  const partPaid = [];
  await forEachAccount(page, async (accountLabel) => {
    const rowAmounts = await page.locator("[data-amount]").allInnerTexts();
    const rowOwings = await page.locator("[data-owing]").allInnerTexts();
    for (let i = 0; i < rowAmounts.length; i += 1) {
      const a = Number(rowAmounts[i].replace(/[$,]/g, ""));
      const o = Number(rowOwings[i].replace(/[$,]/g, ""));
      if (o > 0 && o !== a) partPaid.push({ accountLabel, i, a, o });
    }
    console.log(`   · ${accountLabel}: ${rowAmounts.length} bill(s)`);
    return rowAmounts.length;
  });
  check(
    partPaid.length > 0,
    `at least one bill owes SOME of its amount, so the two columns are provably different` +
      (partPaid.length
        ? `: on ${partPaid[0].accountLabel}, charged $${partPaid[0].a.toFixed(2)} and owing $${partPaid[0].o.toFixed(2)}`
        : " — every bill on every account owes all or nothing, so this fixture cannot prove BR-CWP-043"),
  );
  if (partPaid.length) {
    figures.push(
      `CWP-027 part-paid bill (${partPaid[0].accountLabel}): amount $${partPaid[0].a.toFixed(2)}, owing $${partPaid[0].o.toFixed(2)}`,
    );
  }

  // Hard rule 3 — a quantity is never bare. Every usage cell carries its unit.
  const usageCells = await page.locator("[data-bill-usage]").allInnerTexts();
  check(usageCells.length > 0, `${usageCells.length} usage cell(s) drawn`);
  for (const cell of usageCells) {
    const text = cell.trim();
    if (text === "—" || text === "") continue;
    // Every `<figure> <unit>` pair in the cell, and there may be several.
    const pairs = text.split("·").map((p) => p.trim()).filter(Boolean);
    for (const pair of pairs) {
      check(
        /^[\d,]+(?:\.\d+)?\s+[A-Za-z]/.test(pair),
        `usage "${pair}" carries an explicit unit (hard rule 3 — never a bare quantity)`,
      );
    }
  }
  console.log(`   · usage cells: ${usageCells.map((u) => u.trim()).join(" | ")}`);

  // `BR-CWP-042` — the corrected pair. The fixture cannot plant one (see the
  // header), so this SKIPS BY NAME rather than passing over an absence.
  // ⚠ **A KNOWN GAP, NOT A SKIP — so the day a corrected pair reaches the
  // fixture this run goes RED and names the row to delete.** The boolean has
  // the SAME sense as `check()`: true means the pair IS on screen.
  const replacedBy = await page.locator("[data-replaced-by]").count();
  const replaces = await page.locator("[data-replaces]").count();
  gaps.known(
    replacedBy > 0 && replaces > 0,
    "BR-CWP-042 — a corrected bill stays in the list naming its replacement, and the replacement names what it replaces",
    {
      defect: "DEF-CWP-4176",
      why:
        "no fixture plants a corrected pair. Wave G task G3 names one and it was never written, " +
        "and cr068-g-fixture.py will not drive single_correction.py, which is human-owned money math",
    },
  );

  // The *Unpaid* filter keeps a part-paid bill — it is unpaid to whoever owes
  // the rest of it, which is why `owing` and not the state word drives it.
  // ⚠ **ADDRESSED BY `data-segment`, NOT BY ITS VISIBLE WORD.** The chips are a
  // `SegmentedControl`, and B14 rule 35 says a catalogue is written in its own
  // language — so `getByRole("button", {name: /unpaid/i})` finds nothing the
  // moment this screen is read in any locale but English, and the step SKIPS
  // while looking like a run that simply had no chip.
  // ⚠ **BACK TO THE ACCOUNT THAT HOLDS THE PART-PAID BILL FIRST.** The walk
  // above leaves the switcher on the LAST account, and this assertion is about
  // a specific row. Run without this and it fails over a correct screen — which
  // is a check looking at the wrong thing, and the first run of this file did
  // exactly that.
  if (partPaid.length) {
    const select = page.locator('[data-account-switcher="select"]');
    if ((await select.count()) > 0) {
      await select.selectOption({ label: partPaid[0].accountLabel });
      await page.waitForTimeout(600);
    }
  }
  const unpaidChip = page.locator('[data-segment="unpaid"]').first();
  if ((await unpaidChip.count()) > 0) {
    await unpaidChip.click();
    await page.waitForTimeout(300);
    const afterOwing = await page.locator("[data-owing]").allInnerTexts();
    check(
      afterOwing.length > 0 && afterOwing.every((o) => Number(o.replace(/[$,]/g, "")) > 0),
      `filter Unpaid leaves ${afterOwing.length} row(s) and every one of them owes something`,
    );
    if (partPaid.length) {
      check(
        afterOwing.some((o) => Number(o.replace(/[$,]/g, "")) === partPaid[0].o),
        `…and the part-paid row ($${partPaid[0].o.toFixed(2)} owing) is still among them`,
      );
    }
    await page.locator('[data-segment="all"]').first().click();
    await page.waitForTimeout(300);
  } else {
    skip("the Unpaid filter chip — no [data-segment=\"unpaid\"] on CWP-027");
  }

  await heldControls(page, "CWP-027");
  await noInternals(page, "CWP-027");
  await page.screenshot({ path: join(OUT, "1-bills.png"), fullPage: true });

  // ═════ 2 · CWP-028 — the bill that adds up, from the DISPLAYED figures ═══
  console.log("\n── 2 · One bill: charges + tax = total, computed off the screen ──");
  const firstBillLink = page.locator("[data-bill-link]").first();
  const billNumber = (await firstBillLink.innerText()).trim();
  await firstBillLink.click();
  await page.waitForSelector('[data-screen="CWP-028"]', { timeout: 20000 });
  console.log(`   · opened ${billNumber}`);

  const lineAmounts = await page.locator("[data-figure]").allInnerTexts();
  check(lineAmounts.length > 0, `${lineAmounts.length} charge line(s) on the bill`);

  // ⚠ **THE ARITHMETIC IS DONE ON THE RENDERED STRINGS** (`US-CWP-033` TC-2:
  // *"asserts `$128.09 + $14.09 = $142.18` from **displayed** strings"*). That
  // is the only check that can catch a screen which rounds correctly in the
  // payload and wrongly in the cell — and rounding is where money screens go
  // wrong (hard rule 2: round only at display).
  // ⚠ **THE FIGURE, NOT THE ROW.** `TotalRow` puts `data-total` on a wrapper
  // whose `innerText` is *"Total for this period\n$201.21"*, and `data-subtotal`
  // belongs to a PER-SERVICE line (*"$121.00 for this service"*). Reading either
  // of those as money fails on a screen that is perfectly correct — so each of
  // the three is addressed by the span that holds only the number.
  const subtotalText = (
    await page.locator('[data-figure="subtotal"]').first().innerText().catch(() => "")
  ).trim();
  const taxText = (
    await page.locator('[data-figure="tax"]').first().innerText().catch(() => "")
  ).trim();
  const totalText = (
    await page.locator('[data-total="bill-total"] span').last().innerText().catch(() => "")
  ).trim();
  const subtotal = expectMoney(subtotalText, "CWP-028 charges before tax");
  const tax = expectMoney(taxText, "CWP-028 tax", { allowZero: true });
  const total = expectMoney(totalText, "CWP-028 total");
  if (Number.isFinite(subtotal) && Number.isFinite(tax) && Number.isFinite(total)) {
    const sum = Math.round((subtotal + tax) * 100) / 100;
    check(
      sum === total,
      `the bill adds up FROM THE DISPLAYED FIGURES: $${subtotal.toFixed(2)} + $${tax.toFixed(2)} = $${sum.toFixed(2)} (screen says $${total.toFixed(2)})`,
    );
    // A total of zero would make the identity above true and meaningless.
    check(total !== 0, "…and the total is not $0.00, which would make that identity vacuous");
  }

  // ⚠ **A RATE SHOWS FOUR DECIMALS, ZEROS KEPT — AND THAT IS THE RULE, NOT A
  // BREACH OF ONE.** `OQ-620`, closed 2026-08-27, PO verbatim: *"What does a
  // tariff rate show? Four ($0.1420). A rate is not money and not a quantity -
  // 4 decimal places"*, worked as `8.290000` per kgal → `$8.2900`.
  //
  // ⚠ **THIS LANE FILED THAT AS A DEFECT FIRST (`DEF-CWP-4153`, now INVALID),
  // AND THE ASSERTION IS WRITTEN THE OTHER WAY ROUND BECAUSE OF IT.** Hard rule
  // 2 says money displays 2 and a quantity at most 2 — but a RATE is a THIRD
  // KIND, because it is multiplied by a quantity before it becomes money, so
  // its precision compounds. Rounding this column would print `$0.00 / kWh`
  // beside a real charge for any sub-cent tariff, which is the hazard `OQ-620`
  // exists to prevent. So the check asserts the ruled behaviour POSITIVELY: a
  // regression to two decimals is the bug, and this goes red on it.
  const rates = (await page.locator("[data-rate]").allInnerTexts())
    .map((r) => r.trim())
    .filter((r) => r && r !== "—");
  console.log(`   · ${rates.length} rate cell(s): ${rates.join(" | ")}`);
  // A per-unit rate only — a PERCENT rate (`4.25%`) is a different kind again
  // and displays two, which is hard rule 2 unchanged.
  const unitRates = rates.filter((r) => r.includes("$"));
  check(
    unitRates.length > 0,
    `${unitRates.length} per-unit rate(s) drawn — the four-decimal check needs one to look at`,
  );
  for (const rate of unitRates) {
    check(
      /\$\d[\d,]*\.\d{4}(?!\d)/.test(rate),
      `rate "${rate}" shows FOUR decimals with its zeros kept (OQ-620, PO 2026-08-27)`,
    );
  }

  // Every quantity cell on the bill carries its unit (hard rule 3).
  const quantities = await page.locator("[data-quantity]").allInnerTexts();
  console.log(`   · ${quantities.length} quantity cell(s): ${quantities.map((q) => q.trim()).join(" | ")}`);
  for (const q of quantities) {
    const text = q.trim();
    if (text === "—" || text === "") continue;
    check(
      /[\d,]+(?:\.\d+)?\s*[A-Za-z]/.test(text),
      `bill quantity "${text}" carries its unit (hard rule 3)`,
    );
  }

  await heldControls(page, "CWP-028");
  await noInternals(page, "CWP-028");
  await page.screenshot({ path: join(OUT, "2-one-bill.png"), fullPage: true });

  // ═════ 3 · CWP-029 — the same bytes, twice ═══════════════════════════════
  console.log("\n── 3 · The bill as it was printed: the same file, hashed twice ──");
  await page.goto(`${PORTAL}/bills/${encodeURIComponent(billNumber)}/document`, {
    waitUntil: "networkidle",
  });
  await page.waitForSelector('[data-screen="CWP-029"]', { timeout: 20000 });

  const pdfUrl = `${BASE}/api/${TENANT}/portal/bills/${encodeURIComponent(billNumber)}/document.pdf`;
  const first = await context.request.get(pdfUrl);
  if (first.ok()) {
    const bytesA = Buffer.from(await first.body());
    const again = await context.request.get(pdfUrl);
    const bytesB = Buffer.from(await again.body());
    const hashA = createHash("sha256").update(bytesA).digest("hex");
    const hashB = createHash("sha256").update(bytesB).digest("hex");
    check(bytesA.length > 0, `the served document is ${bytesA.length} bytes, not empty`);
    check(hashA === hashB, `two downloads are byte-identical (BR-CWP-045) — sha256 ${hashA.slice(0, 16)}…`);
    writeFileSync(join(OUT, "3-printed-bill.pdf"), bytesA);
  } else {
    skip(`the printed document — the server answered ${first.status()} for ${billNumber}`);
  }
  // The drawing frames the issued page; `DEF-CWP-3983` was it being a sentence
  // and a link. Either the preview or a stated absence — never a blank panel.
  const hasPreview = (await page.locator("iframe, embed, object, [data-document-preview]").count()) > 0;
  const statedAbsence = (await page.locator("[data-document-absent]").count()) > 0;
  check(
    hasPreview || statedAbsence,
    hasPreview
      ? "the issued page is FRAMED on screen, not merely offered as a download"
      : "no copy was kept, and the screen says so in words rather than drawing a blank panel",
  );
  await heldControls(page, "CWP-029");
  await noInternals(page, "CWP-029");
  await page.screenshot({ path: join(OUT, "3-printed-bill.png"), fullPage: true });

  // ═════ 4 · CWP-031 — what was sent, and by which route ═══════════════════
  console.log("\n── 4 · Documents and letters: named for what they are, with their route ──");
  await page.goto(`${PORTAL}/documents`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-031"]', { timeout: 20000 });
  const docRows = await page.locator('[data-screen="CWP-031"] tbody tr').count();
  const docNames = await page.locator("[data-document-name]").allInnerTexts();
  check(docRows > 0, `the documents table has ${docRows} row(s)`);
  if (docRows === 0) {
    skip("everything about CWP-031's rows — no documents on this fixture");
  } else {
    // `DEF-CWP-3969` — every row was named after its KIND, so five rows read
    // "Bill". A name has to distinguish one row from the next.
    const distinct = new Set(docNames.map((n) => n.trim()));
    check(
      distinct.size > 1 || docNames.length === 1,
      `${docNames.length} document(s) carry ${distinct.size} distinct name(s) — a name that repeats on every row names nothing (DEF-CWP-3969)`,
    );
    console.log(`   · documents: ${[...distinct].slice(0, 6).join(" | ")}`);
  }
  await heldControls(page, "CWP-031");
  await noInternals(page, "CWP-031");
  await page.screenshot({ path: join(OUT, "4-documents.png"), fullPage: true });

  // ═════ 5 · CWP-041 — the bounce is two rows, and one of them is red ══════
  console.log("\n── 5 · Payments: a bounce as two rows, the reversal above the row it undoes ──");
  await page.goto(`${PORTAL}/payments`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-041"]', { timeout: 20000 });

  // ⚠ **ACROSS EVERY ACCOUNT, for the same reason step 1 is.** The bounce is on
  // one of the landlord's three accounts and the switcher does not open on it,
  // so a single-account run SKIPS `BR-CWP-061` over a database that holds it.
  let states = [];
  let bounceAccount = null;
  await forEachAccount(page, async (accountLabel) => {
    const seen = (await page.locator("[data-chip]").allInnerTexts()).map((s) =>
      s.trim().toUpperCase(),
    );
    const rowCount = await page.locator('[data-screen="CWP-041"] tbody tr').count();
    console.log(`   · ${accountLabel}: ${rowCount} row(s) — ${seen.join(" · ") || "(none)"}`);
    if (bounceAccount === null && seen.some((s) => s.includes("BOUNCE"))) {
      states = seen;
      bounceAccount = accountLabel;
    }
    return rowCount;
  });
  // Land on the account that holds the bounce so the row-level checks below
  // look at the rows the states above came from.
  if (bounceAccount !== null) {
    const select = page.locator('[data-account-switcher="select"]');
    if ((await select.count()) > 0) {
      await select.selectOption({ label: bounceAccount });
      await page.waitForTimeout(600);
    }
  }
  const moneyRows = page.locator('[data-screen="CWP-041"] tbody tr');
  const moneyCount = await moneyRows.count();
  check(moneyCount > 0, `the money list has ${moneyCount} row(s) — the bounce checks need them`);
  if (bounceAccount !== null) {
    console.log(`   · the bounce is on ${bounceAccount}`);
  }

  const bouncedAt = states.findIndex((s) => s.includes("BOUNCE"));
  const reversedAt = states.findIndex((s) => s.includes("REVERS"));
  if (bouncedAt === -1) {
    skip(
      "BR-CWP-061, the bounce — no returned payment on this fixture. Run cr068-g-fixture.py. NOT a pass.",
    );
  } else {
    check(reversedAt !== -1, "the payment the bounce undoes is on screen too — a bounce is TWO rows");
    check(
      reversedAt === bouncedAt + 1,
      `the reversal (row ${bouncedAt + 1}) sits DIRECTLY above the row it undoes (row ${reversedAt + 1})`,
    );
    // The negative sign is the server's and the row is the danger tier.
    const bouncedRow = moneyRows.nth(bouncedAt);
    const amountText = (await bouncedRow.locator("[data-amount]").first().innerText()).trim();
    check(
      amountText.startsWith("-") || amountText.startsWith("−"),
      `the reversal is a NEGATIVE amount: "${amountText}" (hard rule 4 — a correction is a new row)`,
    );
    figures.push(`CWP-041 reversal amount = ${amountText}`);
    // ⚠ **PER CELL AND NOT PER ROW** (`13-wireframe-delta` 41.3): the two rows
    // were right and only the CHIP was red, so date, how and reference all read
    // like a payment that went through. BOTH halves are asserted, because a
    // check that only counted red cells would pass on a screen painting both.
    const dangerOnBounced = await bouncedRow.locator('[class*="danger"]').count();
    const undoneRow = moneyRows.nth(reversedAt);
    const dangerOnUndone = await undoneRow.locator('[class*="danger"]').count();
    check(dangerOnBounced > 0, `the reversal's cells are drawn in the danger tier (${dangerOnBounced} cell(s))`);
    check(
      dangerOnUndone < dangerOnBounced,
      `…and the row beneath it is NOT — ${dangerOnUndone} danger cell(s) there, so the two rows read differently`,
    );
  }

  // Every displayed amount on the money list is 2-dp money.
  const moneyAmounts = await page.locator('[data-screen="CWP-041"] [data-amount]').allInnerTexts();
  for (const a of moneyAmounts) {
    check(MONEY.test(a.trim()), `money list amount "${a.trim()}" is drawn to 2 decimals`);
  }
  console.log(`   · amounts: ${moneyAmounts.map((a) => a.trim()).join(" · ")}`);

  // `BR-CWP-051` — a write-off carries no reason code in the body.
  const bodyText = await page.locator("body").innerText();
  check(
    !/\bWO-[A-Z_]+\b|\breason_code\b/i.test(bodyText),
    "no write-off reason code anywhere in the body (BR-CWP-051)",
  );
  // `OQ-1340` wording constraint — this list is NOT a permanent record of a
  // corrected payment reference, and must not say that it is.
  check(
    !/permanent record|permanently recorded/i.test(bodyText),
    "the money list does not describe itself as a permanent record (OQ-1340 is OPEN)",
  );

  await heldControls(page, "CWP-041");
  await noInternals(page, "CWP-041");
  await page.screenshot({ path: join(OUT, "5-payments.png"), fullPage: true });

  // ═════ 6 · every Pay control, on every screen that draws one ═════════════
  console.log("\n── 6 · Every Pay control: a live door, or disabled with its reason ──");
  const paySurfaces = [
    { path: "/pay-now", screen: "CWP-038" },
    { path: "/payment-methods", screen: "CWP-039" },
    { path: "/autopay", screen: "CWP-040" },
  ];
  for (const surface of paySurfaces) {
    await page.goto(`${PORTAL}${surface.path}`, { waitUntil: "networkidle" });
    const drawn = await page.locator(`[data-screen="${surface.screen}"]`).count();
    check(drawn === 1, `${surface.path} draws ${surface.screen}`);
    // ⚠ **A HOLDING SCREEN LEFT IN THE DOM IS A FAILURE**, not a state: the
    // phase-5 routes each answered one until their lane replaced it.
    const holding = await page.locator("[data-holding-screen]").count();
    check(holding === 0, `${surface.screen} is the real screen, not a holding page`);
    await heldControls(page, surface.screen);
    await noInternals(page, surface.screen);
    await page.screenshot({ path: join(OUT, `6-${surface.screen}.png`), fullPage: true });
  }

  // ═════ 7 · a forced click on a held control writes NOTHING ═══════════════
  console.log("\n── 7 · Forcing a held control: no payment row, no gateway call ──");
  const before = await context.request.get(`${BASE}/api/${TENANT}/portal/payments`);
  const beforeRows = before.ok() ? (await before.json()).money.length : -1;
  await page.goto(`${PORTAL}/pay-now`, { waitUntil: "networkidle" });
  const heldButtons = page.locator('[data-held="true"] button');
  const heldButtonCount = await heldButtons.count();
  // ⚠ **A KNOWN GAP, and it is the one that matters most in this wave.**
  // `CWP-038`'s Pay control is disabled and says NOTHING — it is a bare
  // disabled button rather than the kit's `HeldButton` — so there is no held
  // control here to force, on the one screen in this wave that takes money.
  // Recorded this way rather than skipped so that the day somebody routes it
  // through `HeldButton`, this run goes RED and names the row to delete.
  gaps.known(
    heldButtonCount > 0,
    "CWP-038's Pay control is HELD through the kit, so it states its reason and can be force-clicked",
    {
      defect: "DEF-CWP-4152",
      why:
        "the button is disabled with no visible reason, against CR-068 R3 and BR-CWP-056; " +
        "the served refusal exists but the screen does not distinguish 'no gateway' from 'no method chosen', " +
        "so the wording was not invented here",
    },
  );
  if (heldButtonCount === 0) {
    console.log("   · nothing to force on CWP-038 — see the gap above");
  } else {
    // `force: true` bypasses the disabled attribute — which is the point: a
    // control that is only VISUALLY disabled would fire its handler here.
    await heldButtons.first().click({ force: true }).catch(() => {});
    await page.waitForTimeout(600);
    const after = await context.request.get(`${BASE}/api/${TENANT}/portal/payments`);
    const afterRows = after.ok() ? (await after.json()).money.length : -2;
    check(
      beforeRows >= 0 && afterRows === beforeRows,
      `forcing a held control wrote no money row: ${beforeRows} before, ${afterRows} after`,
    );
  }

  // ═════ 8 · the empty state, opened deliberately ══════════════════════════
  console.log("\n── 8 · A customer with no payments: a sentence, never a blank table ──");
  const second = await context.newPage();
  await signIn(second, HOUSEHOLDER_EMAIL);
  await second.goto(`${PORTAL}/payments`, { waitUntil: "networkidle" });
  await second.waitForSelector('[data-screen="CWP-041"]', { timeout: 20000 });
  const emptyRows = await second.locator('[data-screen="CWP-041"] tbody tr').count();
  const emptyState = second.locator("[data-money-empty]");
  const hasEmptyState = (await emptyState.count()) > 0;
  if (emptyRows === 0) {
    check(hasEmptyState, "with no payments the screen states what will fill it (B14 rule 17)");
    if (hasEmptyState) {
      const words = (await emptyState.first().innerText()).trim();
      check(words.length > 0, `…and the sentence is not blank: "${words}"`);
    }
  } else {
    skip(`the empty state — the householder has ${emptyRows} payment row(s), so it cannot be seen here`);
  }
  await second.screenshot({ path: join(OUT, "8-empty.png"), fullPage: true });
  await second.close();

  // ═════ 9 · what it cost, measured (11-response-times.md §5) ══════════════
  await timings.report({
    targets: [
      { id: "RT-2", match: "/portal/auth/sign-in", p95: 900 },
      { id: "RT-6", match: "/portal/bills", p95: 900 },
    ],
  });

  await browser.close();

  console.log("\n── money read off the screen ──");
  for (const figure of figures) console.log(`   ${figure}`);

  if (skipped.length) {
    console.log(`\n── ${skipped.length} step(s) SKIPPED — no data to look at, and a skip is not a pass ──`);
    for (const one of skipped) console.log(`   ⏭ ${one}`);
  }

  // ⚠ **THE EXIT CODE COMES FROM `gaps.report`, NOT FROM `failures` ALONE.**
  // It is 0 only when nothing failed AND no recorded gap has quietly closed —
  // and it prints both counts side by side every time, because
  // `0 failures, 0 known gaps` and `0 failures, 2 known gaps` must never look
  // the same to a reader (law 7's fifth shape).
  console.log("\n── what this run did and did not prove ──");
  process.exit(gaps.report(failures));
})().catch((error) => {
  console.error(error);
  process.exit(2);
});
