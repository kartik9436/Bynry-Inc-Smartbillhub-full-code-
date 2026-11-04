/**
 * RENDERED-OUTPUT CHECK — CR-068 wave L, "Overdue: the ladder, its cost, and
 * the three protections", in a real browser.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: no gate in this repository looks at
 * rendered output, and nine defects in one day were found this way and by
 * nothing else. PO ruling 2026-09-03: *"ensure you do web walkthorugh before
 * you sign off the user story or build"*. `10-execution-plan.md` task `L4`
 * names this file; **it did not exist until 2026-09-06**, while the wave's
 * stamp said all four stories were built and tested.
 *
 * ⚠ **AND THIS WAVE HAS A SECOND REASON THAT IS ITS OWN: IT IS ABOUT MONEY AND
 * ABOUT PROTECTIONS PEOPLE RELY ON.** A wrong figure here is the first number
 * a frightened customer reads, and a missing sentence on `CWP-064` is a
 * household that believes a hold is permanent, stops paying, and is cut the
 * week it lapses. Four of this wave's rules are about what a screen does NOT
 * say — an unmapped rung drawn as an absence, a plan hold with no invented
 * date, a moratorium card with no button, an absent page where there is
 * nothing to report — and **an absence is invisible to every other check this
 * repo has.**
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   eval "$(10-scripts/proof-db.sh clone cwpl --export)"
 *   DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
 *     python3 06-backend/manage.py migrate && \
 *     python3 06-backend/manage.py seed_portal_demo
 *   # the wave's own state — see cr068-l-fixture.py for why it is not in the seeder
 *   DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
 *     python3 10-scripts/render-checks/cr068-l-fixture.py
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8142 --noreload &
 *   (cd 07-frontend && ./node_modules/.bin/vite build && \
 *      PORT=4342 API_PROXY_TARGET=http://127.0.0.1:8142 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4342 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr068-l-overdue-and-protections.mjs
 *
 * ⚠ **BUILD THE BUNDLE, AND BUILD IT IN THE TREE YOU ARE PROVING.** A stale
 * `dist/` means every assertion passes or fails about a build nobody is
 * shipping. On 2026-09-06 this lane's worktree had no `node_modules` at all,
 * `vite build` never ran, and a *successful* build log written by ANOTHER lane
 * into the shared scratchpad read exactly like this one's — the run was one
 * command away from proving a sibling's bundle. `ls 07-frontend/dist/index.html`
 * in YOUR OWN tree before you believe a build.
 *
 * ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** A mid-run reseed
 * looks exactly like a broken screen.
 *
 * ── WHAT IT CLICKS (the wave L demo script, 10-execution-plan.md 586-612) ──
 *   1  `/overdue` (`CWP-057`) — `$412.60 is overdue by 19 days`, and the
 *      timeline is THIS ACCOUNT'S OWN RECORD: due, reminder, first notice,
 *      and a disconnection date that reads *no earlier than*.
 *   2  The cost panel — the parts are ADDED UP IN THE BROWSER and compared
 *      with the subtotal the screen printed, so a total that agrees because
 *      both sides are zero cannot pass. The demo script's `$657.60` is
 *      checked for and its absence REPORTED with the reason.
 *   3  The five-day account — the rung renders as an ABSENCE and neither
 *      neighbour's chip nor the ten-day date is anywhere in the DOM.
 *   4  `/help-paying` (`CWP-056`) — three routes; the moratorium states a fact
 *      and **contains no control**; a certificate ask returns a reference and
 *      says the document goes to the office; and **no protection row appears
 *      on `CWP-064` afterwards** (`BR-CWP-089`), counted before and after.
 *   5  `/protections` (`CWP-064`) — three cards, three DIFFERENT sentences,
 *      the plan hold with no date and none invented, and the debt warning.
 *   6  `/money-back` (`CWP-045`) — the refund and its four steps, the credits
 *      with the bill each was used on, the separating sentence; then a credit
 *      is issued between two loads and the second load must differ
 *      (`BR-CWP-047`).
 *   7  An account in good standing — all three pages state their absence.
 *   8  No database id and no internal code on any of them (B14 rule 31, 32),
 *      every money figure displayed to exactly two decimals (hard rule 2),
 *      and no `data-holding-screen` anywhere.
 */

import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

import { attachTimings } from "./lib/timings.mjs";
import { Gaps } from "./lib/knownGaps.mjs";

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
 * The browser binary — **checked to EXIST, not merely asked for.**
 *
 * ⚠ **THE INHERITED HELPER FALLS BACK ONLY ON A THROW, AND THE FAILURE HERE IS
 * NOT A THROW.** `chromium.executablePath()` cheerfully returned
 * `/opt/pw-browsers/chromium-1234/chrome-linux64/chrome` on a machine that has
 * `chromium-1194`: the pinned playwright-core and the installed browser bundle
 * are different revisions, so the path is well-formed, wrong, and never raises.
 * The `try/catch` in `cr068-e-getting-in.mjs` therefore cannot reach its own
 * fallback — a catch block that is unreachable by construction, which is
 * hard-won law 7's *structurally incapable of failing* one layer down.
 * **So the answer is verified with `existsSync` before it is trusted.**
 */
function resolveChromium() {
  let candidate = null;
  try {
    candidate = chromium.executablePath();
  } catch {
    candidate = null;
  }
  if (candidate && existsSync(candidate)) return candidate;
  const found = execFileSync("bash", [
    "-lc",
    "ls -d /opt/pw-browsers/chromium-*/chrome-linux/chrome 2>/dev/null | head -1",
  ])
    .toString()
    .trim();
  if (!found) {
    throw new Error(
      `no chromium found. playwright-core asked for ${candidate ?? "(nothing)"}, which is not on disk, ` +
        `and /opt/pw-browsers has no chromium-*/chrome-linux/chrome either.`,
    );
  }
  if (candidate) {
    console.log(`   • playwright-core wanted ${candidate}, which is absent; using ${found}`);
  }
  return found;
}

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4342";
const TENANT = "pine-hill";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr068-l";
const VIEWPORT = { width: 1440, height: 1000 };
const PORTAL = `${BASE}/${TENANT}/portal`;

const OVERDUE_EMAIL = process.env.SMOKE_OVERDUE ?? "l-overdue@example.test";
const FIVEDAY_EMAIL = process.env.SMOKE_FIVEDAY ?? "l-fiveday@example.test";
const CLEAR_EMAIL = process.env.SMOKE_CLEAR ?? "l-clear@example.test";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "Elm-Street-1408";

// ── the demo script's own figures. NOT computed here: a walkthrough that
//    derived them would be asserting its own arithmetic. ──────────────────
const OWED = "$412.60";
const DAYS = 19;
const RECONNECTION_FEE = "$95.00";
const SUBTOTAL_WITHOUT_DEPOSIT = "$507.60";
const DRAWN_TOTAL = "$657.60";
const REFUND = "$89.80";
const CREDIT = "$25.88";
const CERTIFICATE_ENDS = "2026-11-30";
const MORATORIUM_FROM = "2026-12-01";
const MORATORIUM_UNTIL = "2027-03-01";

mkdirSync(OUT, { recursive: true });

/** Where the disconnection row sits in the ladder, or -1. */
function cutIndex(ladder) {
  return ladder.findIndex((row) => /disconnect/i.test(row));
}

const failures = [];
const findings = [];
/**
 * ⚠ **A CHECK THAT IS RED BY DESIGN IS A CHECK NOBODY READS**, and this wave
 * has four gaps that are open on purpose. They are recorded rather than noted,
 * because a `note()` can never tell anybody when the product GROWS the thing —
 * a known gap goes red in both directions and names the row to delete.
 */
const gaps = new Gaps();
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}
/** Something the browser saw that no test asserts — reported, never silent. */
function note(message) {
  console.log(`   • ${message}`);
  findings.push(message);
}

/** B14 rule 31 and rule 32 — never an id, never an internal code, on screen. */
const FORBIDDEN = [
  /\bBR-[A-Z]{3}-\d{3,5}(?!\d)/,
  /\bOQ-(?:[A-Z]{3}-)?\d{3,5}(?!\d)/,
  /\bDEF-(?:[A-Z]{3}-)?\d{3,5}(?!\d)/,
  /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
];

async function noInternals(page, where) {
  const text = await page.locator("body").innerText();
  for (const pattern of FORBIDDEN) {
    check(!pattern.test(text), `${where}: nothing matching ${pattern} on screen (B14 rule 31)`);
  }
  check(
    (await page.locator("[data-holding-screen]").count()) === 0,
    `${where}: no holding screen survived`,
  );
}

/**
 * Every `$n.nn` on the page, as strings.
 *
 * ⚠ **CLAUDE.md hard rule 2 — money is DISPLAYED to two decimals**, whatever
 * it is stored to. The server sends `412.6000`; a screen that printed that is
 * the defect, and it is invisible to a `toContain("412.6")` assertion.
 */
async function moneyOnScreen(page) {
  const text = await page.locator("body").innerText();
  return [...text.matchAll(/\$-?[\d,]+(?:\.\d+)?/g)].map((m) => m[0]);
}

/**
 * Every money figure on the page is displayed to two decimals.
 *
 * ⚠ **`expectMoney` IS REQUIRED AND IS NOT A CONVENIENCE.** `[].every(...)` is
 * `true`, so this check passes vacuously on a screen with no money on it — the
 * exact shape of a check that cannot fail. Each caller therefore states
 * whether it expects money at all, and a screen that says `true` and shows
 * none is a FAILURE rather than a silent pass. `CWP-056` says `false` and its
 * emptiness is REPORTED, because the drawing puts the customer's own `$412.60`
 * in the *Spread it out* card and the product's copy carries no figure.
 */
async function assertTwoDecimals(page, where, { expectMoney }) {
  const money = await moneyOnScreen(page);
  if (expectMoney) {
    check(money.length > 0, `${where}: there is money on the screen to check (${money.length} figures)`);
  } else if (money.length === 0) {
    note(`${where}: no money figure anywhere on the screen`);
  }
  const wrong = money.filter((figure) => !/^\$-?[\d,]+\.\d{2}$/.test(figure));
  check(
    wrong.length === 0,
    `${where}: every money figure is displayed to 2 decimals (hard rule 2)` +
      (wrong.length ? ` — offenders: ${wrong.join(", ")}` : ` — ${money.length} checked`),
  );
}

/**
 * Does this text name this date, in whatever format the tenant has set?
 *
 * ⚠ **THIS EXISTS BECAUSE THIS WALKTHROUGH WALKED STRAIGHT INTO THE TRAP IT WAS
 * WARNED ABOUT.** Three of its own assertions compared the screen against the
 * ISO string the SERVER sends — `certEnds.includes("2026-11-30")` — so they
 * passed while the product printed a raw machine date to a customer, and went
 * RED the moment it was repaired to `11/30/2026`. That is precisely wave F's
 * finding: *five of the six tests touching dates asserted the broken text, so
 * they passed on the fault and went red on the repair.*
 *
 * **So the assertion is about the DATE, not about its spelling.** The tenant
 * picks the format (`usePortalDate`, and it may legitimately be `DD/MM/YYYY`,
 * `MM/DD/YYYY` or the server's own string when nothing is set), and a
 * walkthrough that pinned one of those would be asserting a setting rather than
 * the product. Year, day and month must all be named; the month may be a
 * number or a word.
 */
const MONTHS = [
  "january", "february", "march", "april", "may", "june",
  "july", "august", "september", "october", "november", "december",
];

function namesTheDate(text, iso) {
  const [year, month, day] = iso.split("-").map(Number);
  const hay = String(text).toLowerCase();
  const hasYear = hay.includes(String(year));
  const hasDay = new RegExp(`\\b0?${day}\\b`).test(hay);
  const hasMonth =
    new RegExp(`\\b0?${month}\\b`).test(hay) ||
    hay.includes(MONTHS[month - 1]) ||
    hay.includes(MONTHS[month - 1].slice(0, 3));
  return hasYear && hasDay && hasMonth;
}

/**
 * No `YYYY-MM-DD` anywhere on a customer's screen.
 *
 * ⚠ **CHECKED AGAINST THE DRAWING, NOT AGAINST THE TESTS.** All four wave L
 * wireframes write `30 November 2026`; the product printed `2026-11-30`, and
 * the DOM tests assert the raw string, so they passed on the fault and would
 * have gone red on the repair. `usePortalDate` already exists and wave M's five
 * screens were moved onto it days ago (`DEF-CWP-4138`); these four were not.
 *
 * ⚠ **AND IT IS A CHECK ON RENDERED OUTPUT, so no fixture can satisfy it** —
 * the server sends ISO on the wire and always will; what this asks is what the
 * customer reads.
 */
async function assertNoMachineDates(page, where) {
  const text = await page.locator("body").innerText();
  const raw = [...text.matchAll(/\b\d{4}-\d{2}-\d{2}(?:T[\d:.+]+)?/g)].map((m) => m[0]);
  check(
    raw.length === 0,
    `${where}: no raw YYYY-MM-DD on a customer's screen (the drawing writes "30 November 2026")` +
      (raw.length ? ` — found ${raw.length}: ${[...new Set(raw)].slice(0, 6).join(", ")}` : ""),
  );
}

function toNumber(figure) {
  return Number(String(figure).replace(/[$,]/g, ""));
}

async function signIn(page, email) {
  await page.goto(`${PORTAL}/sign-in`, { waitUntil: "networkidle" });
  await settled(page, "CWP-015");
  await page.fill("#portal-email", email);
  await page.fill("#portal-password", PASSWORD);
  await page.getByRole("button", { name: /sign in/i }).click();
  await page.waitForSelector('[data-portal-frame="shell"]', { timeout: 20000 });
}

async function signOut(page) {
  //: The session is a cookie; clearing it is the same as signing out and
  //: does not depend on a control this wave does not own.
  await page.context().clearCookies();
}

/** The fixture, in the mode that changes one figure between two page loads. */
function issueAnotherCredit() {
  return execFileSync(
    "python3",
    [join(process.cwd(), "10-scripts", "render-checks", "cr068-l-fixture.py"), "--spend-a-credit"],
    { env: { ...process.env }, encoding: "utf8" },
  ).trim();
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const timings = attachTimings(context);
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });
  console.log(`cr068-l: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);

  // ═════ 1 · the ladder, and it is THIS ACCOUNT'S OWN RECORD ═══════════════
  console.log("\n── 1 · what happens if this is not paid ──");
  await signIn(page, OVERDUE_EMAIL);
  await page.goto(`${PORTAL}/overdue`, { waitUntil: "networkidle" });
  await settled(page, "CWP-057");

  // ⚠ **THE SCREEN MUST BE IN ITS NORMAL STATE BEFORE ANYTHING IS ASSERTED
  // ABOUT IT.** `DEF-WRK-4121` shipped a dispatcher who could not raise a work
  // order on any non-empty list, because every test used the empty one. Here
  // the empty state is `data-not-overdue`, and on it every assertion below
  // would pass over nothing at all.
  check(
    (await page.locator("[data-not-overdue]").count()) === 0,
    "the account IS overdue — the ladder has something to say (not the empty state)",
  );

  const headline = (await page.locator("[data-headline]").innerText()).trim();
  check(headline.includes(OWED), `the headline states ${OWED}: "${headline}"`);
  check(headline.includes(String(DAYS)), `…and ${DAYS} days: "${headline}"`);

  const steps = page.locator("[data-timeline-step]");
  const stepCount = await steps.count();
  check(stepCount > 1, `the timeline has rows to read (${stepCount})`);
  const ladder = [];
  for (let i = 0; i < stepCount; i += 1) {
    ladder.push((await steps.nth(i).innerText()).replace(/\s+/g, " ").trim());
  }
  for (const row of ladder) console.log(`      ${row}`);
  check(
    ladder.some((row) => /payment was due/i.test(row)),
    "the ladder opens with the day it was due",
  );
  // ⚠ **NAMED, NOT COUNTED.** A first draft asserted *two rows matching
  // /notice/* and went red on a correct screen, because the reminder rung is
  // labelled `Reminder` and contains no such word. Counting a pattern is how a
  // walkthrough reports a product defect it has invented itself; each rung the
  // fixture wrote is therefore asserted BY NAME.
  check(
    ladder.some((row) => /reminder/i.test(row)),
    "…the reminder that was actually sent",
  );
  check(
    ladder.some((row) => /ten-day notice/i.test(row)),
    "…the ten-day notice that was actually sent",
  );
  // ⚠ **THE STEP AT WHICH A HOUSEHOLD CAN STILL ACT.** `CWP-057.png` and the
  // demo script both put *Final notice — around 15 Sep* between the notice
  // already sent and the disconnection. The case carries `next_step_due` and
  // `_timeline` has a `notice_next` branch for exactly this row.
  // ⚠ **IDENTIFIED BY ITS SHAPE, NOT BY ITS LABEL.** The row's label is the
  // TIER's name (*Final notice*, *Ten-day notice*), which depends on how far
  // this particular case has climbed; what makes it P43's fifth rung is that
  // it is a NOTICE that has not happened yet, so it reads *no earlier than*.
  // Asserting the label would tie this check to one fixture's tier.
  const nextNotice = ladder.find(
    (row) => /notice/i.test(row) && /no earlier than/i.test(row),
  );
  check(
    nextNotice !== undefined,
    `…and the NEXT notice, before the disconnection step (P43's fifth rung): "${nextNotice ?? "MISSING"}"`,
  );
  if (nextNotice !== undefined && cutIndex(ladder) >= 0) {
    check(
      ladder.indexOf(nextNotice) < cutIndex(ladder),
      "…and it comes BEFORE the disconnection, which is the order that makes it useful",
    );
  }
  const cut = ladder.find((row) => /disconnect/i.test(row));
  check(cut !== undefined, `…and the disconnection step: "${cut ?? "MISSING"}"`);
  if (cut !== undefined) {
    // ⚠ Nothing in this product advances a tier on a date (`DEF-320`), so the
    // stored date is a FLOOR. A screen that printed it as a promise tells a
    // household it has until a day the utility never agreed to.
    check(/no earlier than/i.test(cut), `…stated as a floor, never as a promise: "${cut}"`);
  }
  const chip = page.locator('[data-chip="tier"]');
  check((await chip.count()) === 1, "the tier is named once, as a chip");
  await assertTwoDecimals(page, "CWP-057", { expectMoney: true });
  await assertNoMachineDates(page, "CWP-057");
  await noInternals(page, "CWP-057");
  await page.screenshot({ path: join(OUT, "1-overdue.png"), fullPage: true });

  // ═════ 2 · what it would cost — ADDED UP IN THE BROWSER ══════════════════
  console.log("\n── 2 · the cost panel, and its arithmetic ──");
  const parts = {};
  for (const part of ["owed", "reconnection_fee", "new_deposit"]) {
    const shown = page.locator(`[data-part="${part}"]`);
    const absent = page.locator(`[data-part-absent="${part}"]`);
    if ((await shown.count()) === 1) {
      parts[part] = (await shown.innerText()).trim();
    } else if ((await absent.count()) === 1) {
      parts[part] = null;
      note(`the cost panel states ${part} as an ABSENCE in words: "${(await absent.innerText()).trim()}"`);
    } else {
      parts[part] = undefined;
    }
  }
  check(parts.owed === OWED, `owed now reads ${parts.owed} (expected ${OWED})`);
  check(
    parts.reconnection_fee === RECONNECTION_FEE,
    `the reconnection fee reads ${parts.reconnection_fee} (expected ${RECONNECTION_FEE}, from the tenant's own CC-RECON row)`,
  );

  const subtotal = (await page.locator('[data-total="if-it-goes-that-far"]').innerText()).trim();
  const subtotalFigure = (subtotal.match(/\$[\d,]+\.\d{2}/) ?? [])[0];
  console.log(`      subtotal row: "${subtotal.replace(/\s+/g, " ")}"`);

  // ⚠ **THE ARITHMETIC IS CHECKED, NOT THE STRING** — and it is checked
  // against a sum this script computes from the PARTS ON SCREEN. A total that
  // matched because both sides were zero would prove nothing, so the parts are
  // required to be non-zero first.
  const known = ["owed", "reconnection_fee"].filter((p) => parts[p] != null);
  const sum = known.reduce((total, p) => total + toNumber(parts[p]), 0);
  check(known.length === 2, `both priced parts are on screen (${known.join(", ")})`);
  check(sum > 0, `…and they are not all zero (they add to ${sum.toFixed(2)})`);
  check(
    subtotalFigure !== undefined && toNumber(subtotalFigure) === sum,
    `the subtotal ${subtotalFigure} equals the parts added up (${sum.toFixed(2)})`,
  );

  // The demo script and the drawing both say `$657.60`, which adds a `$150.00`
  // new deposit. Nothing in this product prices one (`OQ-CWP-1600`), so this
  // is REPORTED rather than asserted either way — the walkthrough's job is to
  // say what the screen printed.
  const bodyText = await page.locator("body").innerText();
  if (bodyText.includes(DRAWN_TOTAL)) {
    note(`the screen prints the drawn total ${DRAWN_TOTAL}`);
  } else {
    note(
      `the screen prints ${subtotalFigure} where the demo script and P43 both say ${DRAWN_TOTAL} — ` +
        `the ${"$150.00"} new deposit is not priced anywhere in this product (OQ-CWP-1600), ` +
        `so the panel states the requirement in words and the row is a SUBTOTAL`,
    );
  }
  check(
    subtotalFigure === SUBTOTAL_WITHOUT_DEPOSIT,
    `…and that subtotal is ${SUBTOTAL_WITHOUT_DEPOSIT} — owed plus the fee, with nothing invented`,
  );
  check(
    (await page.locator("[data-subtotal-note]").count()) === 1,
    "…and the row says in words that something is missing from it",
  );

  // The two doors this screen offers, and the one the drawing offers that it
  // does not. `P43` draws `Ask for a plan` AND `Pay $412.60` in the head.
  const askForPlan = page.getByRole("link", { name: /ask for a payment plan/i });
  check((await askForPlan.count()) >= 1, "*Ask for a payment plan* is offered (BR-CWP-066: ask, never apply)");
  const payControl = page.getByRole("link", { name: /^pay\b/i });
  const payButton = page.getByRole("button", { name: /^pay\b/i });
  const payCount = (await payControl.count()) + (await payButton.count());
  gaps.known(
    payCount > 0,
    'a Pay control beside it — P43 draws "Pay $412.60" in the same head',
    {
      defect: "DEF-CWP-4143",
      why:
        "a customer who opens this screen because they have been told their supply may be cut " +
        "cannot pay from it, and cannot even see that paying is possible — there is no control " +
        "at all, not even a held one with a reason, while /pay-now is live one address away",
    },
  );
  check(
    (await page.locator("[data-held-by]").count()) === 1,
    "the hold is named on the screen about the debt (BR-CWP-091)",
  );
  check(
    (await page.locator("[data-stop-it]").count()) === 1,
    "…and the screen says the customer can stop this",
  );
  await page.screenshot({ path: join(OUT, "2-cost.png"), fullPage: true });

  // ═════ 3 · the five-day rung, as an ABSENCE ══════════════════════════════
  console.log("\n── 3 · a rung the vocabulary cannot name ──");
  await signOut(page);
  await signIn(page, FIVEDAY_EMAIL);
  await page.goto(`${PORTAL}/overdue`, { waitUntil: "networkidle" });
  await settled(page, "CWP-057");
  check(
    (await page.locator("[data-not-overdue]").count()) === 0,
    "this account is overdue too — the absence being tested is the TIER, not the ladder",
  );
  check(
    (await page.locator('[data-tier="absent"]').count()) === 1,
    "the unmapped rung is stated as an absence, in words (BR-CWP-092)",
  );
  check((await page.locator('[data-chip="tier"]').count()) === 0, "…and no chip is drawn for it");
  const fiveDayText = await page.locator("body").innerText();
  for (const neighbour of ["Ten-day notice", "Final notice"]) {
    check(
      !fiveDayText.includes(neighbour),
      `…and never a neighbour's name: "${neighbour}" is not on the screen`,
    );
  }
  await page.screenshot({ path: join(OUT, "3-unmapped.png"), fullPage: true });

  // ═════ 4 · help paying — three doors, one of which is not a door ═════════
  console.log("\n── 4 · help paying ──");
  await signOut(page);
  await signIn(page, OVERDUE_EMAIL);

  // ⚠ Counted BEFORE the ask, so `BR-CWP-089` is proved by a DIFFERENCE
  // rather than by a number that happens to look right.
  await page.goto(`${PORTAL}/protections`, { waitUntil: "networkidle" });
  await settled(page, "CWP-064");
  const protectionsBefore = await page.locator("[data-protection]").count();
  check(protectionsBefore > 0, `there are protections to count before the ask (${protectionsBefore})`);

  await page.goto(`${PORTAL}/help-paying`, { waitUntil: "networkidle" });
  await settled(page, "CWP-056");
  const routes = await page.locator("[data-errand]").count();
  check(routes === 3, `three routes are offered (${routes})`);
  for (const route of ["payment_plan", "medical_certificate", "level_pay"]) {
    check(
      (await page.locator(`[data-errand="${route}"]`).count()) === 1,
      `…including ${route}`,
    );
  }

  const moratorium = page.locator("[data-moratorium]");
  check((await moratorium.count()) === 1, "the moratorium is stated");
  const moratoriumText = (await moratorium.innerText()).replace(/\s+/g, " ").trim();
  console.log(`      moratorium: "${moratoriumText}"`);
  check(
    namesTheDate(moratoriumText, MORATORIUM_FROM) && namesTheDate(moratoriumText, MORATORIUM_UNTIL),
    `…with its dates READ FROM THE RECORD (${MORATORIUM_FROM} → ${MORATORIUM_UNTIL}), never written ` +
      `into the copy — and named in the TENANT's format, not the wire's`,
  );
  // ⚠ **THE ABSENCE IS THE POINT.** Nobody applies for a weather moratorium,
  // so the card carries no control at all — not a disabled one.
  check(
    (await moratorium.locator("button, a").count()) === 0,
    "…and there is no control inside it — nobody applies for a moratorium",
  );

  await page.getByRole("button", { name: /send a certificate/i }).click();
  await page.waitForSelector("[data-ask-sent]", { timeout: 20000 });
  const sent = (await page.locator("[data-ask-sent]").innerText()).trim();
  const bring = (await page.locator("[data-bring-document]").innerText()).trim();
  console.log(`      after the ask: "${sent}" / "${bring}"`);
  check(sent.length > 0, "the ask returns a reference to quote");
  check(
    /office/i.test(bring),
    `…and says where the document goes: "${bring}"`,
  );
  check(
    /nothing is on hold/i.test(bring),
    "…and says plainly that no hold is in place yet (BR-CWP-089)",
  );
  await assertTwoDecimals(page, "CWP-056", { expectMoney: false });
  await assertNoMachineDates(page, "CWP-056");
  note(
    "CWP-056's *Spread it out* card reads \"Pay what you owe over up to twelve months\" — " +
      "P42 draws the customer's own figure there (\"Pay $412.60 over up to twelve months\")",
  );
  await noInternals(page, "CWP-056");
  await page.screenshot({ path: join(OUT, "4-help-paying.png"), fullPage: true });

  await page.goto(`${PORTAL}/protections`, { waitUntil: "networkidle" });
  await settled(page, "CWP-064");
  const protectionsAfter = await page.locator("[data-protection]").count();
  check(
    protectionsAfter === protectionsBefore,
    `the certificate form created NO protection row (${protectionsBefore} before, ${protectionsAfter} after) — BR-CWP-089`,
  );

  // ═════ 5 · three lifetimes, three sentences ══════════════════════════════
  console.log("\n── 5 · what is protecting your supply ──");
  const kinds = ["medical_certificate", "payment_plan", "weather_moratorium"];
  const sentences = [];
  for (const kind of kinds) {
    const card = page.locator(`[data-protection="${kind}"]`);
    check((await card.count()) === 1, `the ${kind} card is drawn`);
    const body = (await page.locator(`[data-protection-body="${kind}"]`).innerText()).trim();
    sentences.push(body);
    console.log(`      ${kind}: "${body}"`);
  }
  // ⚠ `BR-CWP-090` — THREE lifetimes, THREE sentences. Three cards carrying
  // one sentence would pass any per-card assertion and break the rule.
  check(new Set(sentences).size === 3, `the three cards say three DIFFERENT things (${new Set(sentences).size} distinct)`);

  const certEnds = (await page.locator('[data-ends="medical_certificate"]').innerText()).trim();
  check(
    namesTheDate(certEnds, CERTIFICATE_ENDS),
    `the certificate names its end date (${CERTIFICATE_ENDS}): "${certEnds}"`,
  );
  check(
    /not permanent/i.test(sentences[0]),
    "…and says IN WORDS that it is not permanent",
  );
  // ⚠ **NO DATE, AND NONE INVENTED.** A plan hold is not a period. An em-dash
  // or a blank here is the customer who believes the hold is permanent.
  check(
    (await page.locator('[data-ends="no-date"]').count()) === 1,
    "the plan hold carries NO end date and none is invented (BR-CWP-090)",
  );
  check(
    /instalment is missed/i.test(sentences[1]),
    "…and says instead what ends it",
  );
  const planChip = (await page.locator('[data-chip="protection-payment_plan"]').innerText()).trim();
  gaps.known(
    !/not started/i.test(planChip),
    `…and the plan hold's chip does not claim it has not started (it reads "${planChip}")`,
    {
      defect: "DEF-CWP-4154",
      why:
        "the chip has three words for four states, so a hold that is not holding BECAUSE THE " +
        "PLAN IS NOT CURRENT reads *Not started yet* beside a start date in the past — which a " +
        "customer reads as *it is coming*, on the one screen that tells them what is protecting " +
        "their supply",
    },
  );
  const moratoriumEnds = (await page.locator('[data-ends="weather_moratorium"]').innerText()).trim();
  check(
    namesTheDate(moratoriumEnds, MORATORIUM_UNTIL),
    `the moratorium runs to ${MORATORIUM_UNTIL} from the record: "${moratoriumEnds}"`,
  );
  // ⚠ **THE DRAWING GIVES TWO OF THE THREE CARDS AN ACTION AND THE THIRD NONE,
  // AND THE THREE-WAY DIFFERENCE IS ITS POINT.** `ProtectionCard` takes an
  // `action` prop and renders it; `OneProtection` passes it on no card.
  const certificateAction = await page
    .locator('[data-protection="medical_certificate"]')
    .locator("button, a")
    .count();
  gaps.known(
    certificateAction > 0,
    "…and the certificate card offers *Send a new certificate* (P50 draws it)",
    {
      defect: "DEF-CWP-4145",
      why:
        "the certificate holding this supply expires on a stated date and the screen that says " +
        "so gives the customer no way to renew it — they are told the hold ends and left to " +
        "work out for themselves that another certificate is what continues it",
    },
  );
  const warning = (await page.locator("[data-hold-warning]").innerText()).trim();
  check(
    /does not stop the debt/i.test(warning),
    `the debt sentence is ON THE SCREEN (BR-CWP-091): "${warning}"`,
  );
  const moratoriumCard = page.locator('[data-protection="weather_moratorium"]');
  check(
    (await moratoriumCard.locator("button, a").count()) === 0,
    "…and the moratorium card has no control here either",
  );
  await assertNoMachineDates(page, "CWP-064");
  await noInternals(page, "CWP-064");
  await page.screenshot({ path: join(OUT, "5-protections.png"), fullPage: true });

  // ═════ 6 · credits and refunds, and they are different things ════════════
  console.log("\n── 6 · money coming back ──");
  await page.goto(`${PORTAL}/money-back`, { waitUntil: "networkidle" });
  await settled(page, "CWP-045");
  check(
    (await page.locator("[data-money-back-empty]").count()) === 0,
    "there is money coming back — not the empty state",
  );
  const refundAmount = (await page.locator("[data-refund-amount]").first().innerText()).trim();
  check(refundAmount === REFUND, `the refund reads ${refundAmount} (expected ${REFUND})`);
  const refundSteps = await page.locator("[data-timeline-step]").count();
  check(refundSteps === 4, `the refund shows four dated steps (${refundSteps})`);
  const clearing = page.locator("[data-clearing-note]");
  check((await clearing.count()) === 1, `…and the last one says how long it takes: "${(await clearing.innerText()).trim()}"`);

  const creditCells = page.locator("[data-credit]");
  const creditsBefore = await creditCells.count();
  check(creditsBefore > 0, `there are credits to read (${creditsBefore})`);
  const creditFigures = [];
  for (let i = 0; i < creditsBefore; i += 1) {
    creditFigures.push((await creditCells.nth(i).innerText()).trim());
  }
  console.log(`      credits: ${creditFigures.join(", ")}`);
  // ⚠ **THE SIGN THE SERVER SENT IS THE SIGN RENDERED.** A credit note is
  // stored at or below zero by a database CHECK; the drawing prints `$25.88`
  // positive. Reported, because which is right is a decision and not a bug the
  // walkthrough may settle.
  check(
    creditFigures.every((f) => f.includes(CREDIT.replace("$", ""))),
    `every credit is ${CREDIT} in magnitude`,
  );
  if (creditFigures.some((f) => f.trim().startsWith("-"))) {
    note(
      `credits render NEGATIVE (${creditFigures[0]}) — P31 draws them positive (${CREDIT}). ` +
        `The screen renders the sign the server sent and takes no absolute value, deliberately.`,
    );
  }
  // `TwoCol` is what CWP-057 and CWP-064 both compose; this screen stacks.
  await settled(page, "CWP-045");
  const twoCol = await page.locator('[data-screen="CWP-045"] [data-twocol]').count();
  gaps.known(
    twoCol > 0,
    "…and the refund and the credits sit side by side (P31, and L2's own T4)",
    {
      defect: "DEF-CWP-4146",
      why:
        "stacked, the two halves read as one list — and telling a credit from a refund is the " +
        "entire job of this screen; a customer expecting money in their bank is instead given a " +
        "reduction on a bill they have not had yet",
    },
  );
  const separating = (await page.locator("[data-separating-sentence]").innerText()).trim();
  check(
    /credit comes off your next bill/i.test(separating) && /refund is money sent back/i.test(separating),
    `the separating sentence is on the screen: "${separating}"`,
  );
  await assertTwoDecimals(page, "CWP-045", { expectMoney: true });
  await assertNoMachineDates(page, "CWP-045");
  await noInternals(page, "CWP-045");
  await page.screenshot({ path: join(OUT, "6-money-back.png"), fullPage: true });

  // ⚠ **`BR-CWP-047` CAN ONLY BE PROVED BY A CHANGE BETWEEN TWO LOADS.** One
  // load cannot tell a cached screen from a live one, so this issues a credit
  // and reloads. A screen that cached would still show `creditsBefore`.
  console.log(`      ${issueAnotherCredit()}`);
  await page.goto(`${PORTAL}/money-back`, { waitUntil: "networkidle" });
  await settled(page, "CWP-045");
  const creditsAfter = await page.locator("[data-credit]").count();
  check(
    creditsAfter === creditsBefore + 1,
    `the second load shows the new figure (${creditsBefore} → ${creditsAfter}) — nothing is cached (BR-CWP-047)`,
  );

  // ═════ 7 · an account with nothing to report ═════════════════════════════
  console.log("\n── 7 · the three absences ──");
  await signOut(page);
  await signIn(page, CLEAR_EMAIL);
  await page.goto(`${PORTAL}/overdue`, { waitUntil: "networkidle" });
  await settled(page, "CWP-057");
  check(
    (await page.locator("[data-not-overdue]").count()) === 1,
    "CWP-057 states one sentence rather than drawing an empty ladder (BR-CWP-093)",
  );
  check(
    (await page.locator("[data-timeline-step]").count()) === 0,
    "…and there is no ladder at all — an empty one reads as *we have sent everything*",
  );
  await page.goto(`${PORTAL}/protections`, { waitUntil: "networkidle" });
  await settled(page, "CWP-064");
  check(
    (await page.locator("[data-protections-empty]").count()) === 1,
    "CWP-064 states one sentence rather than three empty cards",
  );
  check((await page.locator("[data-protection]").count()) === 0, "…and draws no card");
  await page.goto(`${PORTAL}/money-back`, { waitUntil: "networkidle" });
  await settled(page, "CWP-045");
  check(
    (await page.locator("[data-money-back-empty]").count()) === 1,
    "CWP-045 states one sentence rather than two empty tables",
  );
  await page.screenshot({ path: join(OUT, "7-absences.png"), fullPage: true });

  // ═════ 8 · what it cost, measured (11-response-times.md §5) ══════════════
  await timings.report({
    targets: [
      { id: "RT-2", match: "/portal/auth/sign-in", p95: 900 },
      { id: "RT-3", match: "/arrears", p95: 600 },
    ],
  });

  await browser.close();
  if (findings.length > 0) {
    console.log(`\nREPORTED — ${findings.length} thing(s) the browser saw that no assertion decides:`);
    for (const finding of findings) console.log(`   • ${finding}`);
  }
  process.exit(gaps.report(failures));
})().catch((error) => {
  console.error(error);
  process.exit(2);
});
