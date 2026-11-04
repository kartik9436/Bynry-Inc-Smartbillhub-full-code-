/**
 * RENDERED-OUTPUT CHECK — CR-068 wave M, "Plans and level pay", in a real
 * browser.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: no gate in this repository looks at
 * rendered output, and nine defects in one day were found this way and by
 * nothing else. PO ruling 2026-09-03: *"ensure you do web walkthorugh before
 * you sign off the user story or build"*. `10-execution-plan.md` named this
 * file at line 629 and **no such file was on disk** — wave M's five screens
 * had never been opened.
 *
 * ⚠ **AND THIS WAVE IS MONEY A CUSTOMER IS COMMITTING TO OVER TIME**, which is
 * the least forgiving kind. A wrong instalment on `CWP-042` is a promise to a
 * customer we cannot keep, so every figure here is asserted as a STRING
 * against the signed one — `BR-CWP-062` and `GT-47`'s own arithmetic — and
 * never recomputed by this file. A check that derives the expected value the
 * same way the product does cannot fail.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   10-scripts/proof-db.sh clone cwpm
 *   export DATABASE_URL="postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_cwpm?sslmode=disable"
 *   export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false
 *   python3 06-backend/manage.py seed_portal_demo
 *   (cd 06-backend && python3 manage.py shell < ../10-scripts/render-checks/cr068-m-fixture.py)
 *
 *   python3 06-backend/manage.py runserver 127.0.0.1:8143 --noreload &
 *   (cd 07-frontend && ./node_modules/.bin/vite build && \
 *      PORT=4343 API_PROXY_TARGET=http://127.0.0.1:8143 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4343 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr068-m-plans-and-level-pay.mjs
 *
 * ⚠ **BUILD THE BUNDLE BEFORE YOU DRIVE IT.** `server.mjs` serves `dist/`, so
 * a stale build means every assertion here passes or fails about a product
 * nobody is shipping.
 *
 * ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** A mid-run reseed
 * looks exactly like a broken screen.
 *
 * ⚠ **THE FIXTURE IS NOT OPTIONAL, AND THAT IS THE POINT** (`DEF-WRK-4121`:
 * a dispatcher shipped who could not raise a work order on any non-empty list,
 * because every test used the empty list — the one state where it worked).
 * After `seed_portal_demo` alone there are **no level-pay rows, no offered
 * plan and no portal login at all**, so `CWP-063` and `CWP-066` render their
 * *nothing here* branches, which are real screens that assert cleanly and
 * prove nothing. `cr068-m-fixture.py` puts the demo script's own state in
 * front of the browser, and this file REFUSES TO RUN if it is not there —
 * a skipped step is announced, never silently passed.
 *
 * ── WHAT IT CLICKS (the wave M demo script, 10-execution-plan.md 613-639) ──
 *   1  `CWP-042` — a real preview on an account that HAS arrears and NO live
 *      plan: the instalment rows sum to the spread to the cent, exactly one
 *      row carries the rounding and it is the LAST, thirteen months is
 *      refused naming 2 and 12, and an even division ($120.00 over six) gives
 *      six of $20.00. The commit is *Ask for this plan ✓* — the verb the PO
 *      ruled (`OQ-1391` closed option (a), 2026-09-04) — and never *apply*.
 *   2  `CWP-043` — six rows reading paid on time · paid on time · paid late ·
 *      due in 9 days · to come · to come, the signed `$22.03`/`$22.05`, and
 *      *fees still apply* because THIS plan elected not to suspend them.
 *   3  `CWP-063` — the offered plan, its three controls in the order Accept ·
 *      Ask for different terms · Decline, all held, and the absent expiry
 *      rendered as an absence rather than an invented date.
 *   4  `CWP-044` — level pay, and on an account short of history the REASON
 *      IN WORDS rather than a figure averaged off a season.
 *   5  `CWP-066` — where level pay stands: `$125.00` a month, `$47.30` ahead,
 *      June settles up, and the ahead/behind direction said in words.
 *   6  Every screen: no database id and no internal code on the page
 *      (B14 rule 31 · rule 32), and no sentence promising a plan ENDS
 *      (`OQ-CWP-1720`, OPEN — the PO ruled 2026-08-11 *"nodrop we chase for
 *      payments until write off"*).
 */

import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

import { Gaps } from "./lib/knownGaps.mjs";
import { attachTimings } from "./lib/timings.mjs";

const require = createRequire(join(process.cwd(), "07-frontend", "package.json"));

// ⚠ **`[data-screen="CWP-…"]` STOPPED MEANING "THIS SCREEN HAS ITS DATA"
// (`DEF-CWP-4941`).** R-10 and R-22 (PO 2026-09-11) require a screen to keep
// its identity while it is READING and when it has FAILED, so `CR-085` step 2
// put the mark on every branch. That is right, and it silently turned every
// `waitForSelector('[data-screen=…]')` in this file into a RACE: the wait now
// resolves against the LOADING card, and the `innerText()` assertions below
// then read *"Reading your…"* instead of the figures they are checking.
//
// It does not fail honestly — on a quiet machine the read wins and everything
// passes; under load the same bundle reports defects that are not there, which
// is the mirror of what a walkthrough exists to catch. **A check whose answer
// depends on the load average is not a check** (hard-won law 7: ask what would
// make this pass — or fail — WRONGLY).
//
// ⚠ `state: "attached"` AND NOT THE DEFAULT `"visible"`: what this asks is
// "has it been drawn", and a screen that draws both halves of the 390/1280
// split hides one with `max-md:`, so "visible" waits for something that is
// `display:none` on purpose.
async function settled(page, screen, timeout = 20000) {
  await page.waitForSelector(`[data-screen="${screen}"]`, { state: "attached", timeout });
  await page
    .waitForSelector(`[data-screen="${screen}"] [data-portal-state="loading"]`, {
      state: "detached",
      timeout,
    })
    .catch(() => null);
}
const { chromium } = require("playwright-core");

/**
 * Where chromium actually is.
 *
 * ⚠ **`chromium.executablePath()` DOES NOT THROW WHEN THE BROWSER IS NOT
 * THERE — it returns a path for the build this `playwright-core` was
 * compiled against**, and on this machine that is
 * `/opt/pw-browsers/chromium-1234/chrome-linux64/chrome` while the installed
 * build is `chromium-1194/chrome-linux`. Every render-check in this directory
 * wraps the call in `try/catch`, which therefore never fires: the fallback is
 * unreachable and the run dies at `browserType.launch`. So the path is
 * TESTED for existence rather than trusted — a helper whose fallback cannot
 * run is a check that cannot fail (hard-won law 7).
 */
function resolveChromium() {
  let declared = null;
  try {
    declared = chromium.executablePath();
  } catch {
    declared = null;
  }
  if (declared && existsSync(declared)) return declared;
  const found = execFileSync("bash", [
    "-lc",
    "ls -d /opt/pw-browsers/chromium-*/chrome-linux/chrome /opt/pw-browsers/chromium-*/chrome-linux64/chrome 2>/dev/null | head -1",
  ])
    .toString()
    .trim();
  if (!found) {
    throw new Error(
      `no chromium on this machine: playwright named ${declared ?? "(nothing)"} and it is not there`,
    );
  }
  return found;
}

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4343";
const TENANT = "pine-hill";
const EMAIL = process.env.SMOKE_EMAIL ?? "plans@example.test";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "Pine-Hill-2026!";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr068-m";
const VIEWPORT = { width: 1440, height: 1000 };

const PORTAL = `${BASE}/${TENANT}/portal`;
const API = `${BASE}/api/${TENANT}/portal`;

// ── the signed figures, typed out ONCE and never recomputed ────────────────
// `BR-CWP-062` / `GT-47`: `(172.20 − 40.00) ÷ 6` is five instalments of
// `$22.03` (`$110.15`) and a final `132.20 − 110.15 = $22.05`. These are
// STRINGS on purpose: the moment this file divides anything it stops being
// able to disagree with the engine.
const PLAN_TOTAL = "$172.20";
const PLAN_DOWN = "$40.00";
const PLAN_SPREAD = "$132.20";
const PLAN_EACH = "$22.03";
const PLAN_FINAL = "$22.05";
const LEVEL = "$125.00";
const AHEAD = "$47.30";

mkdirSync(OUT, { recursive: true });

const failures = [];
const skipped = [];
/** ⚠ **THE WIREFRAME GAPS THIS RUN LEAVES OPEN, EACH WITH A DEFECT AND A
 *  REASON.** A walkthrough that exits 1 forever teaches its reader that red is
 *  its normal colour, and then a real regression lands in a pile of expected
 *  ones and is invisible — which is what happened to `G103` for 165 commits.
 *  These pass while the gap is open, are COUNTED and printed either way, and go
 *  RED the day the product grows the thing and this file still says it has not. */
const gaps = new Gaps();
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}
/** ⚠ A DECLARED BLIND SPOT WITH NO NUMBER IS INDISTINGUISHABLE FROM AN EMPTY
 *  ONE (hard-won law 7). Anything this run could not exercise is COUNTED and
 *  printed beside what it did. */
function skip(message) {
  console.log(`   ~ SKIPPED: ${message}`);
  skipped.push(message);
}

/**
 * An i18n key that reached the screen because no catalogue has the string.
 *
 * ⚠ **THIS CHECK EXISTS BECAUSE THE RUN THAT WROTE IT MISSED THE THING IT
 * CATCHES.** `DEF-CWP-4137`'s fix moved the offer's consequence from
 * `miss_two_ends_it` to `missed_we_get_in_touch` in the server AND in eleven
 * catalogues — and the catalogue half was not in the commit. The server then
 * served a code no catalogue could word, and `CWP-063` rendered the literal
 * string `portal.planOffer.consequence.missed_we_get_in_touch` to the customer.
 *
 * **Every absence check in this file passed over it**, correctly and uselessly:
 * the screen genuinely does not say *plan ends*, and a raw key satisfies
 * "does not say the wrong thing" perfectly. What found it was the POSITIVE
 * half of the same assertion in the DOM test — *does it say the right thing* —
 * which is the general lesson: **an assertion that only forbids can be
 * satisfied by rubble.**
 */
const RAW_I18N_KEY = /\bportal\.[a-zA-Z]+\.[a-zA-Z0-9_.]+\b/;

/** B14 rule 31 and rule 32 — never a database id, never an internal code. */
const FORBIDDEN = [
  RAW_I18N_KEY,
  /\bBR-[A-Z]{3}-\d{3,5}\b/,
  /\bOQ-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /\bDEF-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /\bUS-[A-Z]{3}-\d{3,5}\b/,
  /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
];

/**
 * `DEF-CWP-4183` — the page heading and the first card's section title are the
 * same string, one line apart, on four of wave M's five screens. Compared
 * CASE-INSENSITIVELY because the card renders its copy uppercase, which is a
 * style and not a difference a reader perceives.
 */
async function headAndCardTitlesDiffer(page, screen) {
  // ⚠ **`SectionTitle` RENDERS A `<p>`, NOT A HEADING** — so the obvious
  // `h2, h3` selector finds nothing, reports the two titles as different, and
  // the gap register calls the gap CLOSED. That is the "looking at the wrong
  // thing" shape (hard-won law 7) and `knownGaps` is what caught it: a row that
  // flips to CLOSED on a screen the picture says is unchanged is a bad
  // assertion, not a fixed product. Found by reading the helper's own failure.
  await settled(page, screen);
  const head = (await page.locator("h1").first().innerText().catch(() => "")).trim();
  const card = (await page
    .locator(`[data-screen="${screen}"] p.uppercase`)
    .first()
    .innerText()
    .catch(() => "")).trim();
  console.log(`   head "${head}" · first card "${card}"`);
  if (head === "") {
    // ⚠ **NO PAGE HEADING AT ALL, WHICH IS A DIFFERENT FAULT AND NOT THIS ONE.**
    // `13-wireframe-delta.md` already records it portal-wide (*"the signed-in
    // portal has no page heads"*, rows X4/X5), and a screen with no title
    // cannot be repeating one. Registering it as a CLOSED duplicate-title gap
    // would have been this file quietly reporting progress that has not
    // happened — so it is counted as a skip instead, with the reason.
    skip(`${screen} has no page heading, so the duplicate-title gap does not apply to it (see 13-wireframe-delta.md X4/X5)`);
    return;
  }
  const same = card !== "" && head.toLowerCase() === card.toLowerCase();
  gaps.known(!same, `${screen}: the page title and the first card's title differ`, {
    defect: "DEF-CWP-4183",
    why: "the card repeats the page heading verbatim instead of naming what it holds, as every wireframe does",
  });
}

async function noInternals(page, where) {
  const text = await page.locator("body").innerText();
  for (const pattern of FORBIDDEN) {
    check(!pattern.test(text), `${where}: nothing matching ${pattern} on screen (B14 rule 31/32)`);
  }
}

/**
 * `OQ-CWP-1720` is OPEN and the PO ruled the opposite of the design on
 * 2026-08-11: *"nodrop we chase for payments until write off"*. The register
 * row states what ships meanwhile — *the screen says only what the code does*
 * — so **no wave M screen may tell a customer a plan ENDS**. Two of the three
 * plan screens carry this assertion in their own DOM tests; `CWP-063` did not,
 * which is why it is applied here to every screen rather than to one.
 */
async function noPlanEndsPromise(page, where) {
  const text = await page.locator("body").innerText();
  check(
    !/plan ends/i.test(text),
    `${where}: does not tell the customer a plan ENDS (OQ-CWP-1720, PO 2026-08-11)`,
  );
  check(
    !/whole balance falls due|whole remaining balance/i.test(text),
    `${where}: does not tell the customer the whole balance falls due (OQ-CWP-1720)`,
  );
}

/** Money on screen is DISPLAYED to two decimals (CLAUDE.md hard rule 2). */
function moneyStringsIn(text) {
  return [...text.matchAll(/\$[\d,]+\.\d+/g)].map((m) => m[0]);
}
function allTwoDecimals(text) {
  return moneyStringsIn(text).every((s) => /\.\d{2}$/.test(s));
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const timings = attachTimings(context);
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });
  console.log(`cr068-m: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);

  // ═════ 0 · sign in, and REFUSE to run against an unseeded database ═══════
  console.log("\n── 0 · the login, and the fixture this run needs ──");
  await page.goto(`${PORTAL}/sign-in`, { waitUntil: "networkidle" });
  await page.fill("#portal-email", EMAIL);
  await page.fill("#portal-password", PASSWORD);
  await page.getByRole("button", { name: /sign in/i }).click();
  await page.waitForSelector('[data-portal-frame="shell"]', { timeout: 20000 });
  check(true, `signed in as ${EMAIL}`);

  const accounts = await (await context.request.get(`${API}/accounts`)).json();
  const held = accounts.accounts ?? [];
  console.log(`   accounts held: ${held.map((a) => a.account_no).join(", ")}`);
  if (held.length < 3) {
    console.log(
      "\nRED — this login holds fewer than three accounts, so wave M's three states " +
        "cannot all be reached. Run 10-scripts/render-checks/cr068-m-fixture.py.",
    );
    await browser.close();
    process.exit(1);
  }

  // ⚠ FIND EACH ACCOUNT BY WHAT IT HOLDS, NOT BY POSITION. The sample estate
  // is generated and its numbers move; a walkthrough pinned to AC-2026-00046
  // reports a product failure when a seed changes.
  let planAccount = null;
  let offerAccount = null;
  let askAccount = null;
  for (const account of held) {
    const current = await (await context.request.get(`${API}/accounts/${account.id}/plans/current`)).json();
    const live = (current.plans ?? []).some((p) => p.live);
    const offer = await (await context.request.get(`${API}/accounts/${account.id}/plans/offer`)).json();
    if (offer.offer) offerAccount ??= account;
    else if (live) planAccount ??= account;
    else askAccount ??= account;
  }
  check(planAccount !== null, `an account holds a LIVE plan (${planAccount?.account_no})`);
  check(offerAccount !== null, `an account holds an OFFERED plan (${offerAccount?.account_no})`);
  check(askAccount !== null, `an account has NO live plan, so CWP-042 can preview (${askAccount?.account_no})`);
  if (!planAccount || !offerAccount || !askAccount) {
    console.log("\nRED — the wave M fixture is not in this database. Run cr068-m-fixture.py.");
    await browser.close();
    process.exit(1);
  }

  // ═════ 1 · CWP-042 — ask for a plan, and the arithmetic on screen ═══════
  console.log("\n── 1 · CWP-042: the instalments, and the remainder on the LAST row ──");
  await openOn(page, "/ask-for-a-plan", "CWP-042", askAccount.id);

  const owing = askAccount.owing ?? null;
  await page.fill("#term-months", "6");
  await page.fill("#first-due", "2026-10-14");
  await page.fill("#up-front", "40.00");
  await page.getByRole("button", { name: /see the instalments/i }).click();
  await page.waitForSelector("[data-instalments]", { timeout: 20000 });

  const rows = await page.locator("[data-instalment]").allInnerTexts();
  const total = (await page.locator('[data-total="spread"], [data-testid="total-spread"]').first().innerText().catch(() => ""))
    .trim();
  console.log(`   instalments on screen: ${rows.join(" · ")}`);
  console.log(`   total on screen:       ${total || "(not found by testKey 'spread')"}`);

  // ⚠ THE ARITHMETIC IS CHECKED ON THE RENDERED STRINGS. Σ rows must equal the
  // total the same screen prints — not a figure this file computed, and not
  // the figure the API returned. If the table and the total ever disagree the
  // customer is the one who finds it.
  check(rows.length === 6, `six instalment rows drawn (${rows.length})`);
  const cents = rows.map((r) => Math.round(Number(r.replace(/[^0-9.]/g, "")) * 100));
  const sum = cents.reduce((a, b) => a + b, 0);
  const printedTotal = Math.round(Number(total.replace(/[^0-9.]/g, "")) * 100);
  check(
    rows.length > 0 && sum > 0,
    `the rows carry real figures (Σ = $${(sum / 100).toFixed(2)}) — not an empty table`,
  );
  if (printedTotal > 0) {
    check(sum === printedTotal, `Σ instalments $${(sum / 100).toFixed(2)} = the printed total $${(printedTotal / 100).toFixed(2)}`);
  } else {
    skip("the total row could not be located on CWP-042 — Σ was not tied out against it");
  }

  const roundingFlags = await page.locator("[data-instalment]").evaluateAll((els) =>
    els.map((el) => el.getAttribute("data-rounding") === "true"),
  );
  check(
    roundingFlags.filter(Boolean).length === 1,
    `exactly one row is flagged as carrying the rounding (${roundingFlags.filter(Boolean).length})`,
  );
  check(roundingFlags[roundingFlags.length - 1] === true, "…and it is the LAST row (BR-CWP-062)");

  await settled(page, "CWP-042");
  const askText = await page.locator('[data-screen="CWP-042"]').innerText();
  check(
    !/\b\d{4}-\d{2}-\d{2}\b/.test(askText),
    "CWP-042 prints no raw ISO date to the customer (DEF-CWP-4138)",
  );
  check(allTwoDecimals(askText), `every money figure on CWP-042 shows two decimals (hard rule 2)`);
  check(
    /ask for this plan/i.test(askText),
    "the commit says ASK — never *apply* or *set up* (OQ-1391 option (a), PO 2026-09-04)",
  );
  check(
    !/\bapply for\b|\bset up a plan\b/i.test(askText),
    "…and no control on the screen implies the customer sets the plan up themselves",
  );
  await noPlanEndsPromise(page, "CWP-042");
  await noInternals(page, "CWP-042");
  await headAndCardTitlesDiffer(page, "CWP-042");

  // ── the wireframe's own layout, asserted on GEOMETRY ──────────────────────
  // The drawing puts the form and its commit on the LEFT and the instalment
  // table in the RIGHT rail. Asked of the browser's box model rather than of
  // the DOM order, because a CSS grid can reorder either one and a class name
  // in the markup proves nothing about what was painted (DEF-974).
  const tableX = await page
    .locator("[data-instalments]")
    .first()
    .evaluate((el) => el.getBoundingClientRect().left)
    .catch(() => null);
  const commitX = await page
    .getByRole("button", { name: /ask for this plan/i })
    .first()
    .evaluate((el) => el.getBoundingClientRect().left)
    .catch(() => null);
  if (tableX !== null && commitX !== null) {
    console.log(`   instalment table at x=${Math.round(tableX)}, commit at x=${Math.round(commitX)}`);
    gaps.known(tableX > commitX, "CWP-042: the instalment table sits in the RIGHT rail, the commit on the left", {
      defect: "DEF-CWP-4182",
      why: "the columns are inverted against the drawing, so the figures being agreed to and the button that agrees are in different columns",
    });
  } else {
    skip("CWP-042's column geometry could not be measured");
  }

  const termTag = await page
    .locator("#term-months")
    .evaluate((el) => el.tagName.toLowerCase())
    .catch(() => "");
  console.log(`   the term field is a <${termTag}>`);
  gaps.known(termTag === "select", "CWP-042: the term is a bounded list, not a free-text box", {
    defect: "DEF-CWP-4182",
    why: "the drawing shows a select reading '6 months'; a text input loses the unit and lets 13 reach the server",
  });

  await page.screenshot({ path: join(OUT, "1-ask-for-a-plan.png"), fullPage: true });

  // ── the even division: the demo script's second case ──────────────────────
  // `$120.00` over six is six of `$20.00` and NO odd final. This is the case
  // that catches a screen which always claims a remainder.
  console.log("\n── 1b · an even division — six of the same, and no odd final ──");
  // ⚠ THE BALANCE COMES FROM THE SPREAD THE SCREEN JUST PRINTED, not from the
  // account list (which does not carry one). `spread = owing − down`, and the
  // down payment was $40.00, so `owing = Σ rows + 40.00`. Choosing a down
  // payment that leaves exactly $120.00 reproduces the demo script's second
  // case on whatever balance this account happens to have — which is the point:
  // the CASE is the even division, not the figure.
  const owingCents = sum + 4000;
  const evenDown = ((owingCents - 12000) / 100).toFixed(2);
  if (Number(evenDown) > 0) {
    await page.fill("#up-front", evenDown);
    await page.getByRole("button", { name: /see the instalments/i }).click();
    await page.waitForTimeout(800);
    const evenRows = await page.locator("[data-instalment]").allInnerTexts();
    console.log(`   instalments on screen: ${evenRows.join(" · ")}`);
    const distinct = new Set(evenRows.map((r) => r.trim()));
    check(distinct.size === 1, `all six instalments are the same figure (${[...distinct].join(", ")})`);
    const note = await page.locator("[data-rounding-note]").count();
    const flagged = await page.locator('[data-instalment][data-rounding="true"]').count();
    check(
      flagged === 0,
      `…and no row is flagged as carrying a rounding (${flagged}) — DEF-CWP-4140`,
    );
    check(
      note === 0,
      "…and the screen does NOT say the last instalment carries a rounding that does not exist",
    );
    await page.screenshot({ path: join(OUT, "1b-even-division.png"), fullPage: true });
  } else {
    skip(
      `this account owes $${(owingCents / 100).toFixed(2)}, which is not enough to leave $120.00 ` +
        "after a down payment, so the even-division case was not driven",
    );
  }

  // ── thirteen months, refused naming the bounds ────────────────────────────
  console.log("\n── 1c · thirteen months, refused ──");
  await page.fill("#term-months", "13");
  await page.fill("#up-front", "40.00");
  await page.getByRole("button", { name: /see the instalments/i }).click();
  await page.waitForSelector("[data-refused]", { timeout: 20000 }).catch(() => null);
  const refused = await page.locator("[data-refused]").innerText().catch(() => "");
  console.log(`   refusal on screen: "${refused.trim()}"`);
  check(refused.trim().length > 0, "thirteen months is refused on screen, not silently ignored");

  // ═════ 2 · CWP-043 — the whole plan record ══════════════════════════════
  console.log("\n── 2 · CWP-043: six rows, the signed figures, and *fees still apply* ──");
  await openOn(page, "/plan", "CWP-043", planAccount.id);
  await settled(page, "CWP-043");
  const planText = await page.locator('[data-screen="CWP-043"]').innerText();

  // ⚠ CHECK THE PLAN HAS ROWS BEFORE ASSERTING ABOUT ROWS. `[].every(...)` is
  // `true`, and a screen drawing its *no plan* branch would pass every
  // assertion below in silence.
  const planRows = await page.locator("[data-instalment]").count();
  check(planRows === 6, `six instalment rows on the plan (${planRows})`);
  if (planRows === 6) {
    for (const figure of [PLAN_EACH, PLAN_FINAL]) {
      check(planText.includes(figure), `the plan shows ${figure} (BR-CWP-062 / GT-47)`);
    }
    check(planText.includes(PLAN_DOWN), `…and ${PLAN_DOWN} paid up front`);
    const states = await page.locator("[data-instalment]").evaluateAll((els) =>
      els.map((el) => el.closest("tr")?.innerText.replace(/\s+/g, " ").trim() ?? ""),
    );
    console.log("   rows:");
    for (const row of states) console.log(`     ${row}`);
    check(
      /paid late/i.test(planText),
      "a PAID LATE row is drawn — its own word and its own tone, neither on-time nor missed",
    );
    check(/to come/i.test(planText), "…and TO COME rows are drawn");
  } else {
    skip("CWP-043 is not showing a six-instalment plan, so the row states were not asserted");
  }

  // `BR-CWP-064` — late-fee suspension is a PER-PLAN election, and THIS plan
  // did not take it, so the panel has to say so.
  check(
    /fees still apply/i.test(planText),
    "the hold panel says FEES STILL APPLY on a plan that did not suspend them (BR-CWP-064)",
  );
  check(
    /new bills still arrive/i.test(planText),
    "…and that new bills still arrive and still have to be paid (BR-CWP-063)",
  );
  check(
    !/\b\d{4}-\d{2}-\d{2}\b/.test(planText),
    "CWP-043 prints no raw ISO date to the customer (DEF-CWP-4138)",
  );
  check(allTwoDecimals(planText), "every money figure on CWP-043 shows two decimals");
  await noPlanEndsPromise(page, "CWP-043");
  await noInternals(page, "CWP-043");
  await headAndCardTitlesDiffer(page, "CWP-043");

  // ⚠ ASSERTED BY ADDRESS, not by label. The wireframe's head carries *Pay the
  // next one* beside *Agreement*; `/pay-now` (`CWP-038`) is live and routed, so
  // this is a door that could point at it today.
  const payDoor = await page.locator('a[href*="/pay-now"], [data-pay-door]').count();
  console.log(`   controls pointing at /pay-now: ${payDoor}`);
  gaps.known(payDoor >= 1, "CWP-043: offers a way to pay the instalment that is due", {
    defect: "DEF-CWP-4181",
    why: "an instalment is shown DUE IN 9 DAYS and there is no pay control of any kind, held or otherwise, over a live CWP-038",
  });
  await page.screenshot({ path: join(OUT, "2-your-plan.png"), fullPage: true });

  // ═════ 3 · CWP-063 — a plan the utility has offered ═════════════════════
  console.log("\n── 3 · CWP-063: the offer, its three controls, and the absent expiry ──");
  await openOn(page, "/plan-offer", "CWP-063", offerAccount.id);
  await settled(page, "CWP-063");
  const offerText = await page.locator('[data-screen="CWP-063"]').innerText();

  const offerRows = await page.locator("[data-instalment]").count();
  check(offerRows === 6, `six instalments on the offer (${offerRows})`);
  for (const figure of [PLAN_TOTAL, PLAN_DOWN, PLAN_SPREAD, PLAN_EACH, PLAN_FINAL]) {
    check(offerText.includes(figure), `the offer shows ${figure}`);
  }

  // The three controls, IN THIS ORDER (`US-CWP-053` §1).
  const order = await page.locator("[data-plan-action]").evaluateAll((els) =>
    els.map((el) => el.getAttribute("data-plan-action")),
  );
  check(
    JSON.stringify(order) === JSON.stringify(["accept", "different-terms", "decline"]),
    `the three controls are in the order Accept · Ask for different terms · Decline (${order.join(" · ")})`,
  );
  // ⚠ IS THE REFUSAL STILL TRUE? (hard-won law 2, mirror clause). These are
  // held on `OQ-CWP-1568` — *may a signed-in customer accept a plan?* — which
  // is OPEN. The day it is ruled these three become live and this assertion
  // is what should go red.
  const heldCount = await page.locator("[data-plan-action] button[disabled], [data-plan-action] [aria-disabled='true']").count();
  console.log(`   held controls: ${heldCount} of ${order.length}`);
  check(
    heldCount === order.length,
    `all three controls are HELD while OQ-CWP-1568 is open (${heldCount}/${order.length})`,
  );
  const heldReason = await page
    .locator("[data-plan-action]")
    .first()
    .evaluate((el) => el.querySelector("[title]")?.getAttribute("title") ?? el.innerText)
    .catch(() => "");
  console.log(`   the reason shown: "${String(heldReason).trim()}"`);
  check(
    String(heldReason).trim().split(/\s+/).length <= 6,
    `the refusal is ${String(heldReason).trim().split(/\s+/).length} words (B14 rule 33)`,
  );

  // `OQ-CWP-1566` — no column holds an offer's expiry, so the screen must say
  // there is no closing date rather than compute one it cannot enforce.
  const expiry = await page.locator("[data-plan-no-expiry]").count();
  const statedExpiry = await page.locator("[data-plan-expiry]").count();
  check(
    expiry === 1 && statedExpiry === 0,
    `the missing expiry is rendered as an ABSENCE, not an invented date (no-expiry=${expiry}, expiry=${statedExpiry})`,
  );
  check(
    !/\b\d{4}-\d{2}-\d{2}\b/.test(offerText),
    "CWP-063 prints no raw ISO date to the customer (DEF-CWP-4138)",
  );
  check(allTwoDecimals(offerText), "every money figure on CWP-063 shows two decimals");
  await noPlanEndsPromise(page, "CWP-063");
  // ⚠ THE POSITIVE HALF. Forbidding the wrong sentence is satisfied by a blank
  // panel or by a raw i18n key; only this says the customer was told the true
  // thing instead (`DEF-CWP-4137`).
  check(
    /we get in touch/i.test(offerText),
    "…and it says what DOES happen — we get in touch, the plan stays open",
  );
  await noInternals(page, "CWP-063");
  await headAndCardTitlesDiffer(page, "CWP-063");
  await page.screenshot({ path: join(OUT, "3-plan-offer.png"), fullPage: true });

  // ═════ 4 · CWP-044 — level pay ══════════════════════════════════════════
  console.log("\n── 4 · CWP-044: level pay, or the reason there is none ──");
  await openOn(page, "/level-pay", "CWP-044", planAccount.id);
  await settled(page, "CWP-044");
  const levelText = await page.locator('[data-screen="CWP-044"]').innerText();
  // ⚠ **THIS SCREEN HAS THREE BRANCHES AND ONLY ONE OF THEM HAS A JOIN
  // BUTTON.** The first draft of this file asserted the join control on every
  // run and went red on a perfectly correct screen — a customer already ON
  // level pay is not offered a way to join it. That is `DEF-WRK-4121`'s lesson
  // aimed back at the checker: assert the branch you are actually in, and say
  // out loud which branches this run did not reach.
  const unavailable = await page.locator("[data-level-pay-unavailable]").count();
  const enrolled = await page.locator("[data-level-pay-enrolled]").count();
  if (enrolled > 0) {
    const enrolledText = await page.locator("[data-level-pay-enrolled]").innerText();
    console.log(`   already enrolled: "${enrolledText.trim()}"`);
    check(
      enrolledText.includes(LEVEL),
      `the *already on level pay* sentence names the amount ${LEVEL}`,
    );
    const join = await page.locator("[data-level-pay-join]").count();
    check(join === 0, "…and no JOIN control is offered to somebody already on it");
    const door = await page.locator('a[href*="/level-pay/standing"], [data-standing-door]').count();
    check(door >= 1, "…and the screen offers the door to where the level pay STANDS");
    skip("CWP-044's JOIN branch was not exercised — this account is already enrolled");
  } else if (unavailable > 0) {
    const reason = await page.locator("[data-level-pay-unavailable]").innerText();
    console.log(`   not offered, and the reason on screen: "${reason.trim()}"`);
    check(
      /month/i.test(reason) && /\d/.test(reason),
      "the reason is IN WORDS and names the months, rather than an empty panel",
    );
    check(!/null|undefined|NaN/i.test(reason), "…and it does not leak a missing value");
    skip("CWP-044's ELIGIBLE branch was not exercised — this account has too few billed months");
  } else {
    check(levelText.includes(LEVEL), `the level reads ${LEVEL}, rounded by the tenant's setting (BR-CWP-054)`);
    const join = await page.locator("[data-level-pay-join]").count();
    check(join === 1, "the join control is drawn");
  }
  check(allTwoDecimals(levelText), "every money figure on CWP-044 shows two decimals");
  await noPlanEndsPromise(page, "CWP-044");
  await noInternals(page, "CWP-044");
  await headAndCardTitlesDiffer(page, "CWP-044");
  await page.screenshot({ path: join(OUT, "4-level-pay.png"), fullPage: true });

  // ═════ 5 · CWP-066 — where level pay stands ═════════════════════════════
  console.log("\n── 5 · CWP-066: what you pay, how far ahead, and when it settles ──");
  await openOn(page, "/level-pay/standing", "CWP-066", planAccount.id);
  await settled(page, "CWP-066");
  const standingText = await page.locator('[data-screen="CWP-066"]').innerText();

  // ⚠ CHECK THE ACCOUNT IS ENROLLED BEFORE ASSERTING ABOUT AN ENROLMENT. The
  // not-enrolled branch renders perfectly and says none of this.
  const notOn = await page.locator("[data-standing-none]").count();
  if (notOn > 0) {
    check(false, "CWP-066 is showing the NOT-ENROLLED branch — the enrolled figures were not asserted");
  } else {
    check(standingText.includes(LEVEL), `you pay ${LEVEL} each month`);
    check(standingText.includes(AHEAD), `…and you are ${AHEAD} ahead`);
    check(/ahead/i.test(standingText), "the direction is said IN WORDS (ahead / behind), not only as a sign");
    check(/june/i.test(standingText), "…and June is named as the month it settles up");
    const changes = await page.locator("table tbody tr").count();
    console.log(`   rows in *when the level changed*: ${changes}`);
    check(changes > 0, "the level-change table has rows — not an empty table asserting nothing");
  }
  check(
    !/\b\d{4}-\d{2}-\d{2}\b/.test(standingText),
    "CWP-066 prints no raw ISO date to the customer (DEF-CWP-4138)",
  );
  check(allTwoDecimals(standingText), "every money figure on CWP-066 shows two decimals");
  await noPlanEndsPromise(page, "CWP-066");
  await noInternals(page, "CWP-066");

  const csv = await page.getByRole("button", { name: /csv/i }).count();
  const csvLink = await page.locator('a[href*="csv"], [data-standing-csv]').count();
  console.log(`   CSV controls on CWP-066: ${csv + csvLink}`);
  gaps.known(csv + csvLink >= 1, "CWP-066: offers the CSV the drawing and the plan both name", {
    defect: "DEF-CWP-4180",
    why: "the wireframe's head has *↓ CSV* and the execution plan's M2 row names it; neither is built",
  });

  const leaving = await page.locator("[data-standing-leaving]").count();
  const leavingText = /if you left today|would owe you/i.test(standingText);
  console.log(`   *if you left today* panel present: ${leaving > 0 || leavingText}`);
  gaps.known(leaving > 0 || leavingText, "CWP-066: says what leaving level pay would settle", {
    defect: "DEF-CWP-4180",
    why: "the drawing's lower rail answers *if you left today* with the variance and where it goes; the figure is already on screen in a tile and the answer is not",
  });
  await page.screenshot({ path: join(OUT, "5-level-pay-standing.png"), fullPage: true });

  // ═════ 6 · what it cost, measured (11-response-times.md §5) ═════════════
  await timings.report({
    targets: [
      { id: "RT-2", match: "/portal/auth/sign-in", p95: 900 },
      { id: "RT-5", match: "/plans/preview", p95: 900 },
    ],
  });

  await browser.close();
  if (skipped.length > 0) {
    console.log(`\n   ${skipped.length} check(s) NOT RUN — a blind spot with a number on it:`);
    for (const s of skipped) console.log(`   ~ ${s}`);
  }
  // ⚠ `gaps.report` prints the failures AND the open gaps, and returns the exit
  // code: 0 while every gap is still open, 1 the moment one CLOSES and its row
  // is stale — which is the half that makes this a register rather than a mute
  // button.
  process.exit(gaps.report(failures));
})().catch((error) => {
  console.error(error);
  process.exit(2);
});

/**
 * Point the shell at one account.
 *
 * ⚠ **NONE OF WAVE M's ADDRESSES CARRIES AN ACCOUNT ID** — a plan belongs to
 * one account and the SWITCHER names it, because a database id in a URL is a
 * database id on screen (B14 rule 31). So the only way to choose which account
 * a screen reads is to move the switcher, and a walkthrough that navigated
 * straight to `/plan` would read whichever account the shell happened to be on.
 */
async function switchTo(page, accountId) {
  const select = page.locator('[data-account-switcher="select"]');
  const count = await select.count();
  if (count !== 1) {
    // ⚠ NOT A SILENT NO-OP. One account legitimately draws a LABEL rather
    // than a control, but on a login holding three the absence of a `<select>`
    // is a broken shell, and a helper that returned quietly here would let
    // every assertion after it run against the wrong account and pass.
    check(false, `the switcher is not a control (found ${count}) — cannot choose an account`);
    return false;
  }
  await select.selectOption(accountId);
  await page.waitForTimeout(600);
  const now = await select.inputValue();
  check(now === accountId, "the switcher moved to the intended account");
  return now === accountId;
}

/**
 * Open one of wave M's screens ON A NAMED ACCOUNT.
 *
 * ⚠ **THE ORDER MATTERS AND IT IS THE OPPOSITE OF THE OBVIOUS ONE.** The
 * chosen account lives in a React context above the router and **deliberately
 * not in the address** — `currentAccount.tsx`: *"a uuid in a URL is a database
 * id on screen"* (B14 rule 31) — so it is held *for the life of the tab* and a
 * full page load resets it to the first account in the set. Switching and then
 * navigating therefore lands on the wrong account with nothing to show for it:
 * the first draft of this file did exactly that and drove `CWP-042` at an
 * account that already held a live plan, which the server correctly refused
 * with a 409 that looked for all the world like a broken screen.
 * **Navigate, then switch.**
 */
async function openOn(page, path, screen, accountId) {
  await page.goto(`${PORTAL}${path}`, { waitUntil: "networkidle" });
  await settled(page, screen);
  await switchTo(page, accountId);
  await settled(page, screen);
  await page.waitForTimeout(500);
}
