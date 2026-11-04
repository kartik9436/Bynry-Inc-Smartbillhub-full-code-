/**
 * RENDERED-OUTPUT CHECK — CR-068 wave F, "Home, my accounts, my details",
 * in a real browser.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: no gate in this repository looks at
 * rendered output, and nine defects in one day were found this way and by
 * nothing else. PO ruling 2026-09-03: *"ensure you do web walkthorugh before
 * you sign off the user story or build"*. `10-execution-plan.md` names this
 * file at wave F task F4 and **it did not exist until 2026-09-06** — thirteen
 * of the plan's walkthroughs are named and were never written, and this was
 * one of them.
 *
 * ⚠ **AND WAVE F HAS A SECOND REASON THAT IS ITS OWN: THIS WAVE IS MOSTLY
 * SHAPE.** Its rules are about a table having a column, a panel having a head,
 * a date being readable by a person, and a control carrying the grammar r10
 * signs off. **Every one of those is invisible to `tsc`, to 391 portal cases
 * and to every gate**, because the text content is identical whether the
 * column is there or not — you have to LOOK. Six of the eight defects this
 * file was written against were found by reading a wireframe beside a screen,
 * and by nothing else.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   10-scripts/proof-db.sh clone cwpf --export      # then export the two lines
 *   export DATABASE_URL=…  DJANGO_SETTINGS_MODULE=config.settings.local
 *   export JOBS_EAGER=false
 *   python3 06-backend/manage.py migrate
 *   python3 06-backend/manage.py seed_portal_demo
 *   (cd 06-backend && python3 manage.py shell \
 *      < ../10-scripts/render-checks/def-cwp-3965-fixture.py)   # the two logins
 *
 *   python3 06-backend/manage.py runserver 127.0.0.1:8140 --noreload &
 *   (cd 07-frontend && ./node_modules/.bin/vite build && \
 *      PORT=4340 API_PROXY_TARGET=http://127.0.0.1:8140 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4340 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr068-f-home-accounts-details.mjs
 *
 * ⚠ **BUILD THE BUNDLE FIRST.** A stale `dist/` means every assertion below
 * passes or fails about a build nobody is shipping.
 *
 * ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** A mid-run reseed
 * looks exactly like a broken screen. Wave F's ports and clone label — `cwpf`,
 * `8140`, `4340` — are chosen not to collide with the lanes running beside it.
 *
 * ── THE FIGURES ARE READ, NOT HARDCODED, AND THAT IS DELIBERATE ───────────
 *
 * ⚠ **THE DEMO SCRIPT'S NARRATIVE NUMBERS ARE NOT IN THIS DATABASE.** Wave F's
 * script tells the story of Maria Alvarez — `$142.18`, four accounts totalling
 * `$872.82`, a deposit of `$150.00` taken on 4 March 2021. `seed_portal_demo`
 * plants a GENERATED estate, so the landlord here holds **three** accounts and
 * the figures move every time the sample data is regenerated. Asserting
 * `$872.82` would be a check that fails on a correct product, which is worse
 * than no check.
 *
 * **So the arithmetic is asserted as a RELATIONSHIP instead:** the total on
 * screen equals the sum of the rows beneath it, to the cent, whatever those
 * rows happen to be. That is what `BR-CWP-015` actually claims — *shown
 * separately and totalled, never merged* — and it holds on any fixture. The
 * run PRINTS every figure it read, so a human can still eyeball them.
 *
 * ── TWO TRAPS BUILT IN FROM THE FIRST LINE ────────────────────────────────
 *
 * ⚠ **1 · ASSERT IN THE STATE THE SCREEN IS NORMALLY IN, NOT THE STATE A
 * FIXTURE DEFAULTS TO (`DEF-WRK-4121`).** A dispatcher shipped who could not
 * raise a work order on any non-empty list, because every test exercised the
 * empty list — the one state where it worked. **So every list assertion here
 * is guarded by a row COUNT first**: `expectRows()` fails when a table it is
 * about to interrogate is empty, rather than sailing through it.
 *
 * ⚠ **AND IT EXITS 0 WITH TWO NAMED GAPS, RATHER THAN 1 FOREVER.** Two things
 * the drawings ask for are knowingly absent (`DEF-CWP-4136`, `DEF-CWP-4137`)
 * and neither is this lane's to invent. Recorded as ordinary failures they made
 * this file **red on every run**, which teaches its reader that red is its
 * normal colour — so the day a real wave-F regression lands, its one failure
 * arrives in a pile of four expected ones and nobody sees it. `G103` sat red
 * for 165 commits exactly that way, on the one gate whose whole job is that a
 * hold cannot rot.
 *
 * They go through `lib/knownGaps.mjs` instead, which is **not silencing,
 * because it fails in BOTH directions**: an open gap is counted and printed and
 * does not fail the run; and **the day somebody builds one, the assertion
 * starts passing and this file goes RED**, naming the row to delete. Both
 * counts print on every run, pass or fail — a declared blind spot with no
 * number attached is indistinguishable from an empty one.
 *
 * ⚠ **2 · `[].every(…)` IS `true`.** A check that cannot fail is worse than no
 * check because it is trusted. Every `every()` below is preceded by a
 * non-empty assertion on the same collection, and the count is PRINTED, so a
 * silently-empty selector reads as `0` in the log instead of as a tick.
 *
 * ── WHAT IT CLICKS (the wave F demo script, 10-execution-plan.md 373–402) ──
 *   1  Home as the householder — four tiles, the lead balance with its DUE
 *      DATE and countdown, usage WITH ITS UNIT, and no tip slot.
 *   2  Home as the landlord — the total across the set, and the *what this
 *      figure leaves out* line said ONCE rather than once per account.
 *   3  All my accounts — rows first, then the total against their sum, the
 *      *Owing* filter dropping the settled row, and ROW ACTIONS AS ICONS
 *      (r10 rule 15; the drawing's own caption insists on it).
 *   4  Add another account — the consequence box before the commit, and the
 *      rail listing what this login already holds WITH BALANCES.
 *   5  My details — the heading, the commit's grammar, and the sign-in panel's
 *      two controls (`Change password`, `Sign out everywhere`).
 *   6  How we contact you — the neutral ALWAYS chip with NO control beside it,
 *      and the paperless panel in whichever of its two states this account is.
 *   7  Your account — the page head, YOUR SERVICES as a table with **Billed
 *      on**, and the deposit/tax panels ABSENT rather than zeroed.
 *   8  Every screen: no database id, no internal code, and every date readable
 *      by a person (B14 rule 31 · rule 32 · rule 35).
 */

import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

import { Gaps } from "./lib/knownGaps.mjs";
import { attachTimings } from "./lib/timings.mjs";

const require = createRequire(join(process.cwd(), "07-frontend", "package.json"));
const { chromium } = require("playwright-core");

/**
 * ⚠ **`chromium.executablePath()` RETURNS A PATH IT HAS NOT CHECKED, AND THE
 * FALLBACK EVERY OTHER RENDER-CHECK USES IS THEREFORE UNREACHABLE.** It is
 * declarative — the path playwright-core WOULD use for the build it was
 * compiled against — so on a machine whose browser bundle is a different
 * revision it returns a string that does not exist and throws nothing. The
 * `try/catch` the other scripts wrap it in can only fire on a throw, so the
 * `ls` never runs and the launch dies with *"executable doesn't exist"*.
 * Checking the path is the whole fix: a fallback guarded by the wrong
 * condition is a fallback that is not there.
 */
function resolveChromium() {
  let declared = null;
  try {
    declared = chromium.executablePath();
  } catch {
    declared = null;
  }
  if (declared && existsSync(declared)) return declared;
  return execFileSync("bash", ["-lc", "ls -d /opt/pw-browsers/chromium-*/chrome-linux/chrome | head -1"])
    .toString()
    .trim();
}

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4340";
const TENANT = process.env.SMOKE_TENANT ?? "pine-hill";
const PORTAL = `${BASE}/${TENANT}/portal`;
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr068-f";
const VIEWPORT = { width: 1440, height: 1000 };

/** Both logins come from `def-cwp-3965-fixture.py`, which picks them by what
 *  they HOLD rather than by name — see its header. */
const HOUSEHOLDER = process.env.SMOKE_HOUSEHOLDER ?? "ana@example.test";
const LANDLORD = process.env.SMOKE_LANDLORD ?? "maria@example.test";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "Pine-Hill-2026!";

mkdirSync(OUT, { recursive: true });

const failures = [];

/**
 * ⚠ **THE TWO THINGS THE DRAWING ASKS FOR THAT THIS PRODUCT KNOWINGLY DOES NOT
 * HAVE.** Both were found by this walkthrough, both are filed, and both were
 * deliberately NOT closed — one needs pricing knowledge the portal is forbidden
 * to hold, the other needs a ruling before a control on a security path is
 * invented. Recording them as `check()` failures made this file **exit 1 on
 * every run**, and a check whose normal colour is red is a check nobody reads:
 * the day a real wave-F regression lands, its one failure arrives in a pile of
 * four expected ones and is invisible. That is hard-won law 7's first shape,
 * and it is not hypothetical — `G103` was red for 165 commits, unread, on the
 * one gate whose whole job is that a hold cannot rot.
 *
 * ⚠ **`known()` TAKES THE SAME BOOLEAN AS `check()` — true means PRESENT.** It
 * is not an inversion and must not be written as one. A known gap goes red in
 * BOTH directions: still absent is counted and printed, and **the day it is
 * built the assertion starts passing and this file FAILS**, naming the row to
 * delete. Without that second half this would be silencing.
 */
const gaps = new Gaps();

function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

/**
 * A list assertion that refuses to run on an empty list (`DEF-WRK-4121`).
 * Returns the count so the caller can print it — a selector that silently
 * matches nothing shows up as `0` rather than as a row of ticks.
 */
function expectRows(count, what) {
  check(count > 0, `${what}: ${count} row(s) — the screen is in its NON-EMPTY state`);
  return count > 0;
}

/** B14 rule 31 and rule 32 — never an id, never an internal code, on screen. */
const FORBIDDEN = [
  /\bBR-[A-Z]{3}-\d{3,5}\b/,
  /\bOQ-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /\bDEF-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
];

async function noInternals(page, where) {
  const text = await page.locator("body").innerText();
  for (const pattern of FORBIDDEN) {
    check(!pattern.test(text), `${where}: nothing matching ${pattern} on screen (B14 rule 31)`);
  }
}

/**
 * ⚠ **A BARE ISO DATE IS A MACHINE FORMAT AND B14 RULE 35 FORBIDS IT ON A
 * CUSTOMER'S SCREEN** — *"it sound like local person language and not
 * mechanical translations of English"*. Every wireframe in this wave draws
 * *14 Sep*, *4 March 2021*, *Issued 30 Aug*; none draws `2026-08-22`.
 *
 * The pattern deliberately does NOT match a date INSIDE a longer token (a bill
 * number, an id), which is why it is anchored on word boundaries and checked
 * against the visible text rather than the HTML.
 */
const ISO_DATE = /\b\d{4}-\d{2}-\d{2}\b/;

async function noMachineDates(page, where) {
  const text = await page.locator("body").innerText();
  const hits = text.match(new RegExp(ISO_DATE, "g")) ?? [];
  check(
    hits.length === 0,
    `${where}: no bare ISO date on screen (B14 rule 35)${hits.length ? ` — found ${hits.length}: ${[...new Set(hits)].slice(0, 6).join(", ")}` : ""}`,
  );
}

/** `"$1,234.56"` → `1234.56`. Returns null when the text holds no money. */
function money(text) {
  const match = /-?\$\s?([\d,]+\.\d{2})/.exec(text ?? "");
  return match ? Number(match[1].replace(/,/g, "")) : null;
}

async function signIn(page, who) {
  await page.goto(`${PORTAL}/sign-in`, { waitUntil: "networkidle" });
  await page.fill("#portal-email", who);
  await page.fill("#portal-password", PASSWORD);
  await page.getByRole("button", { name: /sign in/i }).click();
  await page.waitForSelector('[data-portal-frame="shell"]', { timeout: 20000 });
}

async function signOutIfPossible(context) {
  await context.clearCookies();
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  //: `11-response-times.md` §5 — this walkthrough PRINTS what it cost and does
  //: not assert that a target was met. It measures what the run already does;
  //: it adds no request of its own.
  const timings = attachTimings(context);
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });
  console.log(`cr068-f: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);

  // ═════ 1 · Home, as the householder ══════════════════════════════════════
  //: The householder is the shape `08-screen-layouts.md` draws `CWP-022` in:
  //: ONE account, an amount owing and a due date. A landlord's home page
  //: cannot show *Due 14 Sep · in 12 days* on its lead tile, because four
  //: accounts have four due dates — so the tile's own rule is only testable
  //: here (`DEF-WRK-4121`'s lesson: assert in the state the screen is
  //: normally in).
  console.log("\n── 1 · Home: one number, one date, one button ──");
  await signIn(page, HOUSEHOLDER);
  await page.goto(`${PORTAL}/home`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-022"]', { timeout: 20000 });

  const tiles = await page.locator("[data-kpi]").count();
  check(tiles >= 3, `the balance strip drew ${tiles} tile(s) (layout: KpiRow × 4)`);

  const owing = (await page.locator("[data-owing]").first().innerText()).trim();
  check(money(owing) !== null, `the lead tile carries a money figure: ${owing}`);

  //: The tile's SECOND line. `08-screen-layouts.md`: *`KpiTile.lead` BALANCE
  //: $142.18 **Due 14 Sep · in 12 days***. A balance with no date is the one
  //: thing this whole screen exists to answer — *do I owe anything AND BY
  //: WHEN* — so its absence is a failure, not a cosmetic gap.
  const leadTile = await page.locator("[data-kpi]").first().innerText();
  check(
    /due/i.test(leadTile),
    `…and states WHEN it is due: ${JSON.stringify(leadTile.replace(/\n/g, " · "))}`,
  );

  //: Hard rule 3 — consumption ALWAYS with an explicit unit, never assumed.
  //: ⚠ **THE UNIT IS ITS OWN `<span>` BESIDE THE FIGURE, NOT PART OF IT.** A
  //: first draft asserted `/\d\s*[A-Za-z]/` over the unit span alone and
  //: failed on a correct screen, because that span holds `kWh` and no digit.
  //: Worth recording: reading `innerText` of a PARENT glues the two together
  //: (`10700kWh`) and reading the CHILD separates them, and neither is what
  //: the customer sees — the browser paints a margin between them. So the two
  //: facts are asserted separately, on the two spans that actually hold them.
  const usageUnits = await page.locator("[data-kpi-unit]").allInnerTexts();
  if (usageUnits.length > 0) {
    check(
      usageUnits.every((u) => /[A-Za-z]/.test(u.trim())),
      `each of the ${usageUnits.length} usage tile(s) names its unit (hard rule 3): ${JSON.stringify(usageUnits)}`,
    );
    //: The drawing writes *4,820 gal* — grouped. `4820` is the same number and
    //: is not the same screen: four digits unseparated is the figure a meter
    //: shows, not the one a person reads.
    const usageValues = await page.locator("[data-kpi-value]").allInnerTexts();
    const ungrouped = usageValues.filter((v) => /^\d{4,}$/.test(v.trim()));
    check(
      ungrouped.length === 0,
      `…and groups its digits (r10/CWP-022 drawing: *4,820 gal*): ${JSON.stringify(usageValues)}`,
    );
  } else {
    console.log("   – no usage tile on this account (no measured service) — skipped");
  }

  //: `BR-CWP-095` — the only home tip is off and out of season, so the SLOT
  //: is absent rather than empty. An absence is invisible to every other kind
  //: of check this repo has, which is why a browser asserts it.
  check(
    (await page.locator("[data-tipbar]").count()) === 0,
    "the tip slot is ABSENT, not an empty box (BR-CWP-095)",
  );

  //: ⚠ **THIS COUNTED TABLE ROWS UNTIL 2026-09-08 AND THERE IS NO TABLE NOW**
  //: (`CR-085` task (c)). The Product Owner asked for a chooser — *"please give
  //: me drop down to select last 6 months - on this - August bill ·
  //: BL-2608-000077"* — so the panel is **YOUR BILL**: one bill, its month and
  //: total in the heading, and the chooser beside it. The old assertion would
  //: have reported `0 row(s)` for ever, which is the shape of a check that has
  //: stopped being able to pass (hard-won law 7).
  const billHeading = (await page.locator("[data-bill-heading]").innerText()).trim();
  check(
    money(billHeading) !== null,
    `YOUR BILL names its month and its total: "${billHeading}"`,
  );
  //: r10 rule 15 — the two ways into the bill are icons, never text links.
  const icons = await page.locator("[data-home-recent-bills] svg").count();
  check(icons > 0, `…and the ways into it are icons: ${icons} (r10 rule 15)`);

  //: ⚠ **THE ASSERTION THE CHOOSER EXISTS FOR: EVERYTHING BELOW IT BELONGS TO
  //: THE MONTH THE HEADING NAMES.** Choosing redraws the panel in place, so the
  //: bill number, the period and the due date follow the heading; a filter
  //: under a fixed heading is exactly what this must not be.
  const chooser = page.locator("[data-select='home-bill-month']");
  if ((await chooser.count()) === 1) {
    const options = await chooser.locator("option").allTextContents();
    check(options.length > 1, `the month chooser offers ${options.length}: ${options.join(" | ")}`);
    const before = (await page.locator("[data-bill]").innerText()).trim();
    await chooser.selectOption({ index: 1 });
    await page.waitForTimeout(300);
    const after = (await page.locator("[data-bill]").innerText()).trim();
    const chosenHeading = (await page.locator("[data-bill-heading]").innerText()).trim();
    check(after !== before, `choosing another month redraws the bill: ${before} → ${after}`);
    check(
      chosenHeading === options[1],
      `…and the heading follows the choice: "${chosenHeading}" vs "${options[1]}"`,
    );
    await chooser.selectOption({ index: 0 });
    await page.waitForTimeout(300);
  } else {
    console.log("   – one bill only, so there is no chooser (a chooser with one option is furniture)");
  }

  //: ⚠ **THE ACCOUNT CARD, AND THE MASK ON IT** — PO 2026-09-08, *"we are not
  //: displaying account # of Customer nmae - ther eis no identifier"*, then
  //: *"you can mask these detials"*. The mask is a property of the PAYLOAD and
  //: this is where it is confirmed to reach a reader's eyes intact.
  const card = page.locator("[data-testid='home-account']");
  check((await card.count()) === 1, "the account card is drawn under the bars");
  const equipment = await page.locator("[data-identity='equipment']").count();
  if (equipment === 1) {
    const references = (await page.locator("[data-identity='equipment']").innerText()).trim();
    check(
      !/meter|cart|inch/i.test(references),
      `equipment is bare references, not descriptions: "${references}"`,
    );
  } else {
    console.log("   – no equipment recorded on this account — skipped");
  }
  for (const row of ["phone", "email"]) {
    const cell = page.locator(`[data-identity='${row}']`);
    if ((await cell.count()) === 1) {
      const value = (await cell.innerText()).trim();
      check(value.includes("\u2022"), `${row} reaches the screen MASKED: "${value}"`);
    }
  }
  check(
    !/licence|license|passport/i.test((await card.innerText()) || ""),
    "no government id on the card — none is served and none is invented",
  );

  await noInternals(page, "Home");
  await noMachineDates(page, "Home");
  await page.screenshot({ path: join(OUT, "1-home-householder.png"), fullPage: true });

  // ═════ 2 · Home, as the landlord ═════════════════════════════════════════
  console.log("\n── 2 · Home: a set, totalled and never merged ──");
  await signOutIfPossible(context);
  await signIn(page, LANDLORD);
  await page.goto(`${PORTAL}/home`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-022"]', { timeout: 20000 });

  const landlordOwing = (await page.locator("[data-owing]").first().innerText()).trim();
  console.log(`   → the landlord's lead tile reads ${landlordOwing}`);
  check(money(landlordOwing) !== null, `the lead tile totals the set: ${landlordOwing}`);

  //: ⚠ **THE SAME SENTENCE, ONCE PER ACCOUNT.** `balances.problems` is
  //: concatenated across the set, so a landlord with three accounts was told
  //: three times, identically, what the figure leaves out — and React was
  //: handed three children with the same key. A gap is a fact about the
  //: FIGURE, so it is said once however many accounts stand behind it.
  const gapLines = await page.locator("[data-home-problems] li").allInnerTexts();
  const uniqueGaps = new Set(gapLines.map((s) => s.trim()));
  check(
    gapLines.length === uniqueGaps.size,
    `the *what this leaves out* list says each thing ONCE: ${gapLines.length} line(s), ${uniqueGaps.size} distinct`,
  );

  await noMachineDates(page, "Home (landlord)");
  await page.screenshot({ path: join(OUT, "2-home-landlord.png"), fullPage: true });

  // ═════ 3 · All my accounts ═══════════════════════════════════════════════
  console.log("\n── 3 · All my accounts: four rows and a total, never one invoice ──");
  await page.goto(`${PORTAL}/accounts`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-023"]', { timeout: 20000 });

  const heading = await page.locator("h1").allInnerTexts();
  check(heading.length === 1, `the screen has exactly one heading: ${JSON.stringify(heading)}`);

  const rowCount = await page.locator("tbody tr").count();
  if (expectRows(rowCount, "the accounts table")) {
    //: `BR-CWP-015` — shown SEPARATELY and totalled for information, never
    //: merged. Asserted as arithmetic against whatever rows exist, because
    //: the demo script's `$872.82` is not in a generated estate.
    //: ⚠ **READ BY COLUMN HEADER, NOT BY A `data-` MARK THIS SCRIPT INVENTED.**
    //: The rows carry no per-cell mark, and adding one only to assert it would
    //: prove that the walkthrough and the screen agree with each other. Finding
    //: the column the way a reader does — by the word above it — also fails
    //: loudly if the column is renamed or removed, which is the point.
    const headers = (await page.locator("thead th").allInnerTexts()).map((h) =>
      h.trim().split("\n")[0].toLowerCase(),
    );
    const balanceIndex = headers.findIndex((h) => h.startsWith("balance"));
    check(balanceIndex >= 0, `the table has a BALANCE column: ${JSON.stringify(headers)}`);
    const balances =
      balanceIndex >= 0
        ? await page.locator(`tbody tr td:nth-child(${balanceIndex + 1})`).allInnerTexts()
        : [];
    check(
      balances.length === rowCount,
      `every row states its own balance: ${balances.length} of ${rowCount}`,
    );
    const sum = balances.reduce((acc, text) => acc + (money(text) ?? 0), 0);
    const totalText = (await page.locator("[data-accounts-total]").innerText()).trim();
    const total = money(totalText);
    console.log(`   → rows ${JSON.stringify(balances)}  total ${totalText}`);
    check(total !== null, `the total line states a figure: ${totalText}`);
    check(
      total !== null && Math.abs(total - sum) < 0.005,
      `the total is the SUM of the rows: ${sum.toFixed(2)} vs ${total?.toFixed(2)} (BR-CWP-015)`,
    );

    //: r10 rule 15 and the drawing's own caption: *"Note the row actions are
    //: icons, not links: view and pay, with anything rarer behind an
    //: overflow."*
    const rowIcons = await page.locator("tbody svg").count();
    check(rowIcons > 0, `the rows carry ICON actions: ${rowIcons} across ${rowCount} row(s) (r10 rule 15)`);

    //: The *Owing* chip drops a settled account. Asserted only when there IS
    //: a settled account to drop — otherwise it is a check that cannot fail.
    const settled = balances.filter((b) => money(b) === 0).length;
    if (settled > 0) {
      //: ⚠ **A MISSING CHIP MUST FAIL THE CHECK, NOT KILL THE RUN.** The first
      //: draft called `.click()` straight out and a chip that is not there threw
      //: a 30-second timeout that ended the walkthrough at step 3 — so steps 4
      //: to 7 reported NOTHING, and the log looked like a crash rather than
      //: like a finding. A walkthrough that stops early is a walkthrough whose
      //: silence you cannot read.
      const owingChip = page.locator("button", { hasText: /^\s*owing\s*$/i }).first();
      const hasChip = (await owingChip.count()) > 0;
      check(hasChip, "the toolbar offers an *Owing* filter chip (r10 rule 12)");
      if (hasChip) {
        await owingChip.click();
        await page.waitForTimeout(600);
        const afterFilter = await page.locator("tbody tr").count();
        check(
          afterFilter === rowCount - settled,
          `the *Owing* chip drops the ${settled} settled row(s): ${rowCount} → ${afterFilter}`,
        );
        const allChip = page.locator("button", { hasText: /^\s*all\s*$/i }).first();
        if ((await allChip.count()) > 0) {
          await allChip.click();
          await page.waitForTimeout(400);
        }
      }
    } else {
      console.log("   – every account owes something; the *Owing* filter has nothing to drop — skipped");
    }
  }

  //: r10 rule 16 — a pagination footer on every list table.
  check(
    (await page.locator(".table-pager").count()) > 0,
    "the list has the shared kit's pagination footer (r10 rule 16)",
  );

  await noInternals(page, "All my accounts");
  await noMachineDates(page, "All my accounts");
  await page.screenshot({ path: join(OUT, "3-accounts.png"), fullPage: true });

  // ═════ 4 · Add another account ═══════════════════════════════════════════
  console.log("\n── 4 · Add another account: what it will do, before it does it ──");
  await page.goto(`${PORTAL}/accounts/add`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-020"]', { timeout: 20000 });

  //: r10 rule 11 — a form that changes service state states what it will do
  //: BEFORE its commit button.
  check(
    (await page.locator("[data-add-account-consequences]").count()) === 1,
    "the consequence box is on the screen before the commit (r10 rule 11)",
  );
  //: r10 rule 10 — required fields carry the asterisk.
  //: r10 rule 10 — required fields carry the brand asterisk on the LABEL.
  //: `FormField` draws it as a `.req` span, so the mark is the kit's and not
  //: this screen's to invent.
  const required = await page.locator("label span[aria-hidden]").count();
  check(required >= 2, `both fields are marked required: ${required} (r10 rule 10)`);

  //: The drawing's rail lists what this login already holds AND WHAT EACH
  //: OWES — the figure is the reason a landlord opens this screen at all.
  //: The rail states how many accounts this login already holds. `data-
  //: already-count` is the FIGURE, so the panel around it is what carries the
  //: rows — read from the panel, and the count is asserted against what the
  //: session actually serves rather than against a number typed here.
  const railCount = Number((await page.locator("[data-already-count]").innerText()).trim());
  const served = await page.evaluate(async (tenant) => {
    const list = await fetch(`/api/${tenant}/portal/accounts`).then((r) => (r.ok ? r.json() : null));
    return list && list.accounts ? list.accounts.length : null;
  }, TENANT);
  check(
    Number.isFinite(railCount) && railCount === served,
    `the rail counts what the session serves: ${railCount} on screen, ${served} served`,
  );
  if (expectRows(railCount, "the *already on this login* rail")) {
    //: The drawing puts the BALANCE beside each address — it is the reason a
    //: landlord opens this screen rather than the account number, which they
    //: are about to type into the box on the left.
    //: Scoped to the RAIL PANEL by its own testid, never to the page. A
    //: page-wide money match would pass on any screen carrying a figure
    //: anywhere — including the balance the shell itself draws — so it could
    //: not fail on the thing it is pointed at.
    //:
    //: ⚠ **AND IT WAITS, WITH A BOUND, BECAUSE THE FIRST VERSION RACED THE
    //: SERVER AND FAILED ON A CORRECT SCREEN.** The rail draws each account's
    //: address immediately and its BALANCE when `my-accounts` lands, falling
    //: back to the account number until then. Read the moment the screen
    //: appears and you catch the fallback — this assertion passed twice and
    //: then failed once on identical code, which is the worst kind of check:
    //: one whose colour depends on how busy the machine is.
    //:
    //: A fixed `waitForTimeout` would only move the race. Polling until the
    //: figure appears AND FAILING WHEN IT NEVER DOES keeps both directions
    //: honest: a slow read passes, a missing balance still fails after five
    //: seconds, and the text it actually saw is printed either way.
    const railPanel = page.locator('[data-testid="add-account-already"]');
    const MONEY = /\$\s?[\d,]+\.\d{2}/;
    let railText = "";
    for (let attempt = 0; attempt < 25; attempt += 1) {
      railText = await railPanel.innerText();
      if (MONEY.test(railText)) break;
      await page.waitForTimeout(200);
    }
    check(
      MONEY.test(railText),
      `…and each row states its balance, as the drawing does: ${JSON.stringify(railText.replace(/\n/g, " · ").slice(0, 120))}`,
    );
  }

  await noInternals(page, "Add another account");
  await page.screenshot({ path: join(OUT, "4-add-account.png"), fullPage: true });

  // ═════ 5 · My details ════════════════════════════════════════════════════
  console.log("\n── 5 · My details: what a customer may change, and what they may not ──");
  await page.goto(`${PORTAL}/my-details`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-024"]', { timeout: 20000 });

  //: `BR-CWP-026` — a legal name is not a form here, and the screen says so
  //: with the route to ask instead.
  const notHere = await page.locator("[data-legal-name]").innerText();
  check(notHere.trim().length > 0, `the screen names what is NOT changed here: ${JSON.stringify(notHere.split("\n")[0])}`);

  //: r10 rule 4 — `Verb ✓` COMMITS. The drawing writes *Save changes ✓*.
  //: Asserted by ROLE rather than by a data mark: the drawing names the
  //: control by its words, and a mark this walkthrough invented would only
  //: prove that the walkthrough and the screen agree with each other.
  const commitButtons = await page.getByRole("button", { name: /save changes/i }).allInnerTexts();
  check(commitButtons.length === 1, `there is one *Save changes* commit: ${JSON.stringify(commitButtons)}`);
  check(
    commitButtons.length === 1 && /✓/.test(commitButtons[0]),
    `…and it carries the ✓ grammar (r10 rule 4): ${JSON.stringify(commitButtons)}`,
  );

  //: `08-screen-layouts.md` CWP-024: `ButtonRow` *Change password* · *Sign out
  //: everywhere*. `sessions/revoke-all` shipped in wave E — a served endpoint
  //: with no door is hard-won law 2 in its second direction.
  for (const [pattern, what] of [
    [/change password/i, "Change password"],
    [/sign out everywhere/i, "Sign out everywhere"],
  ]) {
    const found = await page.getByRole("button", { name: pattern }).count();
    gaps.known(found === 1, `the sign-in panel offers *${what}*`, {
      defect: "DEF-CWP-4137",
      why:
        "the panel says how many devices are signed in and offers nothing to act on it; " +
        "sign-out-everywhere even has a served endpoint from wave E with no door. Both are " +
        "NEW controls on a security path — revoking every session including the current one " +
        "is behaviour nobody has signed, and there is no in-session password flow at all — " +
        "so drawing either would be inventing it, and holding it would add two more holds to " +
        "a portal that has just been audited for holds that rot",
    });
  }

  await noInternals(page, "My details");
  await noMachineDates(page, "My details");
  await page.screenshot({ path: join(OUT, "5-my-details.png"), fullPage: true });

  // ═════ 6 · How we contact you ════════════════════════════════════════════
  console.log("\n── 6 · How we contact you: post is a floor, not a switch ──");
  await page.goto(`${PORTAL}/my-details/preferences`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-025"]', { timeout: 20000 });

  const grid = page.locator("[data-preference-grid]");
  check((await grid.count()) === 1, "the grid is the shared kit's PreferenceGrid (B14 rule 36)");
  const gridRows = await grid.locator("tbody tr").count();
  if (expectRows(gridRows, "the WHAT WE SEND grid")) {
    //: `BR-BIL-036` / `BR-CWP-087` — print is the FLOOR. The POST cell states
    //: the rule and offers NO control, because a switch that quietly does
    //: nothing is worse than an honest sentence. Asserted on the POST COLUMN
    //: rather than on the whole grid, which carries real switches elsewhere.
    const postCells = grid.locator("tbody tr td:nth-child(2)");
    const postText = await postCells.allInnerTexts();
    check(
      postText.length === gridRows,
      `every row has a POST cell: ${postText.length} of ${gridRows}`,
    );
    const postControls = await postCells.locator("button, input, select").count();
    check(
      postControls === 0,
      `…and the POST column offers no control at all: ${postControls} (BR-CWP-087)`,
    );
  }

  //: `BR-CWP-087` R4/R6 — the consent carries the date it was agreed, and a
  //: customer who was never asked is TOLD they were never asked rather than
  //: shown an off switch. Both states are legitimate; the screen must be in
  //: one of them and say which.
  const consent = await page.locator("[data-consent-state]").count();
  const neverAsked = await page.locator("[data-no-consent]").count();
  check(
    consent + neverAsked >= 1,
    `the paper panel is in exactly one stated position: consent=${consent} never-asked=${neverAsked} (BR-CWP-087 R4/R6)`,
  );
  if (consent > 0) {
    const agreed = await page.locator("[data-agreed-on]").count();
    check(agreed === 1, "a recorded consent shows the date it was agreed (BR-CWP-087 R4)");
  }

  await noInternals(page, "How we contact you");
  await noMachineDates(page, "How we contact you");
  await page.screenshot({ path: join(OUT, "6-preferences.png"), fullPage: true });

  // ═════ 7 · Your account ══════════════════════════════════════════════════
  console.log("\n── 7 · Your account: the facts that are not on a bill ──");
  await page.goto(`${PORTAL}/account`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-065"]', { timeout: 20000 });

  //: `08-screen-layouts.md` CWP-065 opens `PageHead` kicker **MY DETAILS** ·
  //: title *Your account* · subtitle. It was drawing straight into a panel.
  const accountHeads = await page.locator("h1").allInnerTexts();
  check(accountHeads.length === 1, `the screen has a page head: ${JSON.stringify(accountHeads)}`);

  //: `Panel` **YOUR SERVICES** `MiniTable` **Service / On since / Billed on**.
  //: The third column is the one a customer cannot get anywhere else — it is
  //: why a trash line costs what it costs.
  //: ⚠ **ASKED AS *IS IT A TABLE WITH THREE COLUMNS*, NOT AS *DOES IT HAVE
  //: ROWS*.** A first draft counted rows and reported *"0 row(s) — the screen
  //: is in its NON-EMPTY state"*, which is true of the selector and MISLEADING
  //: to a reader: the panel is drawn and full, as a two-column key-value list.
  //: The gap is its SHAPE, so the check has to say that or the next person
  //: reads it as an empty screen and goes looking for the wrong bug (law 7:
  //: a check's output must distinguish pass from fail TO A READER).
  const servicesPanel = page.locator('[data-testid="your-account-services"]');
  const servicesDrawn = (await servicesPanel.count()) > 0;
  check(servicesDrawn, "the YOUR SERVICES panel is on the screen");
  if (servicesDrawn) {
    const asTable = await servicesPanel.locator("table").count();
    const headers = (await servicesPanel.locator("th").allInnerTexts()).map((h) => h.trim());
    //: `08-screen-layouts.md` CWP-065: `MiniTable` **Service / On since /
    //: Billed on**. The third column is the one a customer cannot get anywhere
    //: else — it is why a trash line costs what it costs.
    gaps.known(
      asTable > 0,
      "YOUR SERVICES is a MiniTable rather than a key-value list (layout CWP-065)",
      {
        defect: "DEF-CWP-4136",
        why:
          "the drawing is a three-column table and the screen draws a two-column list; the " +
          "shape follows the missing column below rather than being wrong on its own",
      },
    );
    gaps.known(
      headers.some((h) => /billed on/i.test(h)),
      "…and it names what each service is BILLED ON",
      {
        defect: "DEF-CWP-4136",
        why:
          "absent from the screen AND from the server's reply — `AccountSummary.services` is " +
          "{code, name, since}. It is the one thing on this screen a customer cannot get from " +
          "a bill (why a trash line costs what it costs), and reaching it needs rating " +
          "knowledge the portal may not hold under CR-068 §2d, so it is a backend job",
      },
    );
  }

  //: ⚠ **THE BODY IS READ THROUGH THE PRODUCT'S OWN DOORS, NOT GUESSED.**
  //: `/summary` is per-account and `CWP-065` deliberately keeps the id out of
  //: the address (B14 rule 31), so the id comes from the account set the
  //: session already serves — the same walk the screen itself makes.
  const summary = await page.evaluate(async (tenant) => {
    const list = await fetch(`/api/${tenant}/portal/accounts`).then((r) => (r.ok ? r.json() : null));
    if (!list || !list.accounts || list.accounts.length === 0) return null;
    const id = list.accounts[0].id;
    return fetch(`/api/${tenant}/portal/accounts/${id}/summary`).then((r) => (r.ok ? r.json() : null));
  }, TENANT);
  check(summary !== null, "the account summary was read from the server");

  //: `US-CWP-031` TC-8 — no deposit ⇒ NO PANEL, never `$0.00`, because a zero
  //: reads as *we took nothing from you* rather than *there is nothing here*.
  //: Which state this account is in comes off the WIRE, so this is a
  //: correspondence between the body and the screen rather than a constant
  //: that only holds on one fixture.
  const depositOnScreen = await page.locator("[data-deposit-held]").count();
  if (summary && summary.deposit === null) {
    check(depositOnScreen === 0, "no deposit is held, so the deposit panel is ABSENT (US-CWP-031 TC-8)");
  } else if (summary && summary.deposit) {
    check(depositOnScreen === 1, "a deposit is held, so the panel is drawn with its date and interest");
  }

  //: The same correspondence for the tax exemption and its lapse date.
  const taxOnScreen = await page.locator("[data-tax-until]").count();
  if (summary && summary.tax_exemption === null) {
    check(taxOnScreen === 0, "no exemption is held, so the tax panel is ABSENT (BR-CWP-093)");
  } else if (summary && summary.tax_exemption) {
    check(taxOnScreen === 1, "an exemption is held, so it is shown with the date it lapses (BR-CWP-053)");
  }

  //: `BR-CWP-052` — the three held-back fields are absent from the BODY, not
  //: merely undrawn. A field that is served and not rendered is still served.
  const bodyText = JSON.stringify(summary ?? {});
  check(bodyText !== "{}", "…and the body was non-empty, so the three checks below mean something");
  for (const forbidden of ["credit_tier", "match_tier", "match_basis"]) {
    check(!bodyText.includes(forbidden), `the body carries no ${forbidden} (BR-CWP-052)`);
  }

  await noInternals(page, "Your account");
  await noMachineDates(page, "Your account");
  await page.screenshot({ path: join(OUT, "7-your-account.png"), fullPage: true });

  // ═════ 8 · what it cost, measured (11-response-times.md §5) ══════════════
  await timings.report({
    targets: [
      { id: "RT-2", match: "/portal/auth/sign-in", p95: 900 },
      { id: "RT-3", match: "/portal/home", p95: 600 },
    ],
  });

  await browser.close();
  //: ⚠ **BOTH COUNTS, ALWAYS, EVEN ON A PASS.** A declared blind spot with no
  //: NUMBER attached is indistinguishable from an empty one — `G32` truthfully
  //: reported *0 unresolved* over twenty-one live refusals it could not see.
  //: `report()` prints the failures and the known gaps side by side and names
  //: every gap, so a reader can tell "nothing is wrong" from "two things the
  //: drawing asks for are missing and this run did not prove them".
  process.exit(gaps.report(failures));
})().catch((error) => {
  console.error(error);
  process.exit(2);
});
