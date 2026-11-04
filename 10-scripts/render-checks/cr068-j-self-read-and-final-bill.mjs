/**
 * RENDERED-OUTPUT CHECK — CR-068 wave J, "Your own reading, and the final
 * bill", in a real browser.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: no gate in this repository looks at
 * rendered output, and nine defects in one day were found this way and by
 * nothing else. PO ruling 2026-09-03: *"ensure you do web walkthorugh before
 * you sign off the user story or build"*.
 *
 * ⚠ **AND THIS WAVE IS A THIRD BUILT, WHICH IS THE POINT RATHER THAN AN
 * EXCUSE.** Of its three stories only `US-CWP-037` — *your final bill* — has a
 * screen. `US-CWP-042` *send your own reading* (`CWP-035`) and `US-CWP-068` *a
 * visit is booked* (`CWP-067`) are two of the ten drawn-and-unbuilt screens
 * `DEF-CWP-3988` counts. **The title's first half is the missing half.** So
 * this file's job is to walk what exists, prove it against the drawings, and
 * make the absence LEGIBLE instead of implied — through `lib/knownGaps.mjs`,
 * which counts and prints every gap and **fails the day one closes**.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   eval "$(10-scripts/proof-db.sh clone cwpj --export)"
 *   export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false
 *   (cd 06-backend && python3 manage.py migrate && python3 manage.py seed_portal_demo)
 *   (cd 06-backend && python3 manage.py shell < ../10-scripts/render-checks/cr068-j-fixture.py)
 *
 *   (cd 06-backend && python3 manage.py runserver 127.0.0.1:8146 --noreload &)
 *   (cd 07-frontend && ./node_modules/.bin/vite build && \
 *      PORT=4346 API_PROXY_TARGET=http://127.0.0.1:8146 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4346 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr068-j-self-read-and-final-bill.mjs
 *
 * ⚠ **THE FIXTURE IS NOT OPTIONAL AND IS NOT A CONVENIENCE.** `seed_portal_demo`
 * plants NO final bill on any account, so `/final-bill` draws its *"when your
 * service ends…"* sentence for every customer in the estate. A run without
 * `cr068-j-fixture.py` would assert cheerfully over an empty page and report a
 * clean walk of a screen it never saw. That is `DEF-WRK-4121` — **assert in the
 * state the screen is normally in, not the fixture's default.**
 *
 * ⚠ **AND IT TAKES TWO LOGINS, WHICH IS THE SAME LESSON ONE LEVEL UP.**
 * `CWP-032` has two halves and a single account can only ever show one:
 * `Settlement.settled` is `path is not None or remainder == 0`, and a refund
 * picks its path automatically, so a *we owe you* bill is `settled` the instant
 * it is read and its *Query this reading* control can never draw. Walking one
 * account would have reported whichever half it happened to land on as the
 * whole screen (wave G's `DEF-WRK-4121`-shaped finding, restated).
 *
 * ── WHAT IT CLICKS (the wave J demo script, 10-execution-plan.md) ─────────
 *   1  The self-read switch — and the address the drawing gives `CWP-035`
 *      (`/usage/submit`) opens nothing, in EITHER switch position.
 *   2  *Send your own reading* — the screen is not built. KNOWN GAP.
 *   3  The nineteen-times warning — no form to type into. KNOWN GAP.
 *   4  A submitted read on no bill — nothing can submit one. KNOWN GAP.
 *   5  The readings screen carries the vocabulary for a customer's own reading
 *      (*You sent it in*) and NO reading can ever wear it.
 *   6  **Your final bill** (`CWP-032`), both halves, on two accounts:
 *      the settling-up lines ADD UP to the total on the screen; *we owe you*
 *      against *you owe us*; the closing reading and its unit; the query route.
 *   7  *A visit is booked* (`CWP-067`) — not built, `OQ-249` open. KNOWN GAP.
 *   8  B14 rule 31/32 — no database id and no internal code on any screen.
 *
 * ⚠ **STEP 5 IS WHERE THE REGISTER WAS STALE, AND IT CHANGES WHAT IS MISSING.**
 * The plan's own demo script says step 5 calls a straight-to-bill path and gets
 * `NotImplementedError("OQ-1393")`. **`OQ-1393` was CLOSED on 2026-09-04** —
 * the PO ruled option (b), *"we accept the reading - and then run the
 * validation and flag it if any issue; you will also ahve to flag that this
 * reading is reacievd from Cosnumer"*. There is no stub to demonstrate and none
 * should be written. `CWP-035` is **unbuilt and no longer blocked**, which is a
 * different and larger statement than the plan makes. `DEF-CWP-4194`.
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
 * ⚠ **`executablePath()` RETURNS A PATH IT NEVER CHECKS, SO A `try/catch`
 * AROUND IT GUARDS THE WRONG FAILURE.** Playwright composes the path from the
 * browser revision its own package expects — `chromium-1234` here — and this
 * machine has `chromium-1194` installed. Nothing throws: the string comes back
 * fine and the LAUNCH fails one line later, naming a browser nobody asked for.
 * Every render-check in this directory carries the `try/catch` form, which is
 * `CLAUDE.md` law 7's *"structurally incapable of failing"* in miniature — the
 * fallback can only run in the one case that does not occur. **So the
 * existence of the file is the check.**
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
    "ls -d /opt/pw-browsers/chromium-*/chrome-linux/chrome 2>/dev/null | head -1",
  ])
    .toString()
    .trim();
  if (!found) {
    throw new Error(
      `no chromium on this machine. playwright wanted ${declared ?? "(nothing)"} and ` +
        "/opt/pw-browsers holds no chromium-*/chrome-linux/chrome",
    );
  }
  if (declared && declared !== found) {
    console.log(`   note: playwright asked for ${declared}, using ${found}`);
  }
  return found;
}

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4346";
const TENANT = "pine-hill";
const PORTAL = `${BASE}/${TENANT}/portal`;
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr068-j";
const VIEWPORT = { width: 1440, height: 1000 };

/** The two leaving customers `cr068-j-fixture.py` plants. */
const REFUND_EMAIL = process.env.SMOKE_REFUND_EMAIL ?? "elm@example.test";
const OWING_EMAIL = process.env.SMOKE_OWING_EMAIL ?? "leaving@example.test";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "Pine-Hill-2026!";

const failures = [];
const skipped = [];
const figures = [];
const gaps = new Gaps();

function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
  return ok;
}

function skip(message) {
  console.log(`   ~ SKIPPED ${message}`);
  skipped.push(message);
}

function record(label, value) {
  figures.push(`${label}: ${value}`);
  console.log(`   · ${label} = ${value}`);
}

/**
 * ⚠ **THE HELPER THIS SCRIPT WOULD BE WORTHLESS WITHOUT.**
 *
 * `[].every(...)` is `true`, so *"every settling-up line is money to two
 * decimals"* PASSES over a panel with no lines in it — and a panel with no
 * lines is exactly what `/final-bill` draws on an account that is not leaving,
 * which is EVERY account until this wave's fixture runs. A claim about "every
 * X" is made in two parts and the first part is that there is an X at all.
 */
function over(items, where, { min = 1, expected = null } = {}) {
  const n = items.length;
  if (expected !== null) {
    check(n === expected, `${where}: ${n} row(s) drawn (expected ${expected}) — nothing below is vacuous`);
  } else {
    check(n >= min, `${where}: ${n} row(s) drawn (need at least ${min}) — nothing below is vacuous`);
  }
  return n > 0;
}

/** B14 rule 31 and rule 32 — never a database id, never an internal code. */
const FORBIDDEN = [
  /\bBR-[A-Z]{3}-\d{3,5}\b/,
  /\bOQ-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /\bDEF-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /\bUS-CWP-\d{3,5}\b/,
  /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
];

async function noInternals(page, where) {
  const text = await page.locator("body").innerText();
  for (const pattern of FORBIDDEN) {
    check(!pattern.test(text), `${where}: nothing matching ${pattern} on screen (B14 rule 31/32)`);
  }
}

/**
 * ⚠ **MONEY DISPLAYS AT TWO DECIMALS AND A RATE AT FOUR** (hard rule 2;
 * `OQ-620`, PO 2026-08-27: *"A rate is not money and not a quantity - 4 decimal
 * places"*). **A four-decimal figure on this screen is NOT a defect to file
 * against the rate rule** — a lane filed exactly that against wave G and was
 * wrong. What this asserts is the narrow, correct thing: every figure in the
 * SETTLING UP panel is a settled money amount, so every one of them shows two.
 */
const MONEY = /^-?\$[\d,]+\.\d{2}$/;

/** `$1,234.56` / `-$1,234.56` → a Number, so lines can be ADDED. */
function money(text) {
  const cleaned = String(text ?? "").replace(/[^0-9.-]/g, "");
  return cleaned === "" ? NaN : Number(cleaned);
}

async function shot(page, name) {
  await page.screenshot({ path: join(OUT, `${name}.png`), fullPage: true });
}

async function signIn(page, email) {
  await page.goto(`${PORTAL}/sign-in`, { waitUntil: "networkidle" });
  await page.fill("#portal-email", email);
  await page.fill("#portal-password", PASSWORD);
  await page.getByRole("button", { name: /sign in/i }).click();
  await page.waitForSelector('[data-portal-frame="shell"]', { timeout: 20000 });
}

async function signOut(page) {
  // The shell is left by going back to the door; a stale session would carry
  // one customer's account into the next customer's assertions, which is the
  // one way this script could report a clean cross-account walk it never did.
  await page.context().clearCookies();
}

/**
 * Read the SETTLING UP panel as a customer sees it: the label/value pairs and
 * the total, as STRINGS off the screen.
 *
 * ⚠ **OFF THE SCREEN AND NOT OFF THE WIRE.** `US-CWP-037` §7's whole subject is
 * that a customer and a clerk must quote the same figure; asserting the payload
 * would prove the server agrees with itself. The arithmetic below is done on
 * the rendered cells for the same reason wave G did it — it is the only place
 * a rounding or a missing line can actually be seen.
 */
async function settlingUp(page) {
  const card = page.locator('[data-testid="final-bill"]');
  const rows = await card.locator("[data-kv]").all();
  const lines = [];
  for (const row of rows) {
    const label = (await row.locator("dt").innerText()).trim();
    const value = (await row.locator("dd").innerText()).trim();
    lines.push({ label, value });
  }
  const totalRow = card.locator('[data-total="settlement"]');
  const total = {
    label: (await totalRow.locator("span").first().innerText()).trim(),
    value: (await totalRow.locator("span").last().innerText()).trim(),
  };
  return { lines, total };
}

(async () => {
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT, acceptDownloads: true });
  const timings = attachTimings(context);
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });
  console.log(`cr068-j: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);

  // ═════════════════════════════════════════════════════════════════════════
  // 1 · THE SWITCH, AND THE ADDRESS THE DRAWING GIVES CWP-035
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 1 · send your own reading: the switch, and what it reaches ──");
  await signIn(page, REFUND_EMAIL);

  // The drawing's own address bar reads `…/portal/usage/submit`. Nothing is
  // routed there. ⚠ This is asserted by what the ROUTER does, not by a 404 from
  // the server: the portal is a single-page app, so an unrouted path returns
  // HTTP 200 with the shell around a not-found panel. A status-code check here
  // would pass on every address in the product and prove nothing.
  await page.goto(`${PORTAL}/usage/submit`, { waitUntil: "networkidle" });
  const submitScreen = await page.locator("[data-screen]").getAttribute("data-screen").catch(() => null);
  record("what /usage/submit opens", submitScreen ?? "(no screen element)");
  gaps.known(
    submitScreen === "CWP-035",
    "the drawing's address /usage/submit opens *Send us your reading* (CWP-035)",
    {
      defect: "DEF-CWP-3988",
      why: "CWP-035 is one of the ten drawn screens with no address in the product. It is UNBLOCKED — OQ-1393 was ruled on 2026-09-04 — and simply unbuilt",
    },
  );
  await shot(page, "1-usage-submit");

  // The one control in the product that names it. `holds.ts` keys this hold by
  // its reason string and `g103_holds_cannot_rot.py` fails the merge the day
  // CWP-035 gains a row in PORTAL_SCREENS — so this refusal cannot rot in the
  // way DEF-CWP-3925 cost a week.
  await page.goto(`${PORTAL}/readings`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-034"]', { timeout: 20000 });
  const held = page.locator('[data-held="true"]').filter({ hasText: /reading/i });
  const heldCount = await held.count();
  check(heldCount >= 1, "CWP-034 draws a HELD *Send a reading* control naming the screen that is missing");
  if (heldCount >= 1) {
    const reason = (await held.first().locator("span").last().innerText()).trim();
    record("the refusal a customer reads", JSON.stringify(reason));
    // B14 rule 33 — a refusal sentence caps at five or six words.
    const words = reason.split(/\s+/).filter(Boolean).length;
    check(words <= 6, `…and it is ${words} words (B14 rule 33 caps a refusal at five or six)`);
  }
  await shot(page, "1-readings-held");

  // ═════════════════════════════════════════════════════════════════════════
  // 2–4 · THE FORM, THE WARNING, AND THE BILL RUN THAT SHOULD EXCLUDE IT
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 2-4 · the form, the nineteen-times warning, the excluded read ──");

  // Each is recorded separately rather than as one "CWP-035 is missing",
  // because they are three different pieces of work and whoever builds the
  // screen needs to see all three come due. The drawing is the specification:
  // a meter picker showing the SERIAL, a date inside the window, a wide
  // spaced-digit dial box, a held photo picker, and a *what happens to it*
  // panel — which is r10 rule 11's "what this will do" box, mandatory on any
  // form that writes service state.
  gaps.known(false, "a form to send a reading: meter, date, dial figure, held photo picker", {
    defect: "DEF-CWP-3988",
    why: "CWP-035 has no address. The drawing specifies a DialInput — the wide spaced-digit control DEF-CWP-3986 records as built for CWP-017 and available to compose",
  });
  gaps.known(false, "the flagged dial goes brand-red and says *about nineteen times your usual*, and can still be sent", {
    defect: "DEF-CWP-3988",
    why: "BR-CWP-070 — a failing reading is shown what it implies and is NOT refused. There is no form, so there is nothing to flag",
  });
  gaps.known(false, "a submitted reading lands awaiting review and appears on NO bill until a clerk clears it", {
    defect: "DEF-CWP-3988",
    why: "BR-CWP-068. POST accounts/{id}/readings does not exist — apps/portal/api.py says so in its own comment — so nothing can be submitted to be excluded",
  });

  // ═════════════════════════════════════════════════════════════════════════
  // 5 · THE VOCABULARY EXISTS AND NOTHING CAN WEAR IT
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 5 · the readings screen already has the words for a reading nobody can send ──");

  // ⚠ **THE PLAN'S STEP 5 IS STALE AND MUST NOT BE BUILT.** It asks for a
  // straight-to-bill path raising `NotImplementedError("OQ-1393")`. That
  // question was CLOSED on 2026-09-04 (option b, plus a provenance flag on
  // EVERY customer reading). There is no boundary to demonstrate. What is
  // demonstrable is the shape of the hole, and it is on this screen.
  await page.goto(`${PORTAL}/readings`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-034"]', { timeout: 20000 });
  const methodCells = await page.locator("[data-how]").all();
  if (over(methodCells, "CWP-034 readings, each stating how it was taken")) {
    const methods = [];
    for (const cell of methodCells) methods.push((await cell.innerText()).trim());
    const distinct = [...new Set(methods)];
    record("how the readings on file were taken", JSON.stringify(distinct));
    // `portal.readings.how.self_read` — *You sent it in* — is written in all
    // eleven catalogues. No row in this product can carry it: `READ_SOURCES` is
    // `("ami", "manual", "import")` and the PO's ruling needs a FOURTH value.
    check(
      !distinct.some((m) => /you sent it in/i.test(m)),
      "no reading says *You sent it in* — the words are written and nothing can produce one",
    );
  }
  gaps.known(false, "a reading whose method reads *You sent it in* (portal.readings.how.self_read)", {
    defect: "DEF-CWP-4194",
    why: "OQ-1393's ruling needs a FOURTH meter_source beside ami/manual/import for the provenance flag; B2 names three and metering READ_SOURCES holds three",
  });
  await shot(page, "5-readings-methods");

  // ═════════════════════════════════════════════════════════════════════════
  // 6 · YOUR FINAL BILL — the half of this wave that is built
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 6a · your final bill, where the deposit comes back (we owe you) ──");
  await page.goto(`${PORTAL}/final-bill`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-032"]', { timeout: 20000 });

  // ⚠ **THE EMPTY STATE IS CHECKED FIRST, BECAUSE IT IS THE ONE THIS SCREEN IS
  // IN BY DEFAULT.** If the fixture did not run, `data-final-none` is present
  // and every assertion below would be over a card holding one sentence.
  const noBill = await page.locator("[data-final-none]").count();
  check(noBill === 0, "this account IS leaving — the *when your service ends* sentence is not the page");
  if (noBill > 0) {
    skip("everything below: cr068-j-fixture.py has not been run against this database");
  } else {
    const head = (await page.locator(".page-header").innerText().catch(() => "")).trim();
    record("the page head", JSON.stringify(head));
    check(/moving out/i.test(head), "the kicker is MOVING OUT — the situation, not the document (drawing P18)");
    check(/your final bill/i.test(head), "…and the title is *Your final bill*");

    const period = (await page.locator("[data-final-period]").innerText()).trim();
    record("the period sentence", JSON.stringify(period));
    check(
      /up to the reading taken on the day you left/i.test(period),
      "the period sentence names the reading it was cut on (drawing P18)",
    );

    const { lines, total } = await settlingUp(page);
    over(lines, "CWP-032 SETTLING UP lines", { expected: 3 });
    for (const line of lines) record(`  ${line.label}`, line.value);
    record("  TOTAL", `${total.label} ${total.value}`);

    // ── the money rules, on the rendered strings ──────────────────────────
    for (const line of lines) {
      check(MONEY.test(line.value), `*${line.label}* displays money at 2 decimals: ${line.value}`);
    }
    check(MONEY.test(total.value), `the total displays money at 2 decimals: ${total.value}`);

    // ⚠ **THE ONE ASSERTION THIS SCREEN EXISTS FOR.** `US-CWP-037`'s subject is
    // *service − deposit − interest = what we owe you*, and a customer checks it
    // by adding the column up. Asserted on the DISPLAYED strings and as
    // ARITHMETIC, never against a literal: `US-CWP-037` carries
    // `golden_tests: []`, so `$89.80` is a story's illustration and the engine's
    // answer for this tenant's rate is whatever it is. A literal here would be
    // the walkthrough asserting the engine's answer back at it.
    const sum = lines.reduce((acc, line) => acc + money(line.value), 0);
    const stated = money(total.value);
    check(
      Math.abs(sum - stated) < 0.005,
      `the three lines ADD UP to the total on the screen: ` +
        `${lines.map((l) => l.value).join(" + ")} = ${sum.toFixed(2)} vs stated ${total.value}`,
    );
    record("the settling-up arithmetic", `${sum.toFixed(2)} (lines) vs ${stated.toFixed(2)} (stated)`);

    check(/we owe you/i.test(total.label), "a deposit larger than the charges reads *We owe you* (BR-CWP-048)");
    check(stated < 0, "…and the figure is the server's signed one, with no Math.abs on the screen");

    // BR-CWP-048 — a REFUND, never a carried credit. Both sentences, in words.
    const consequence = (await page.locator("[data-consequence-code]").allInnerTexts()).map((s) => s.trim());
    over(consequence, "CWP-032 *what happens next* bullets", { min: 2 });
    record("what happens next", JSON.stringify(consequence));
    check(
      consequence.some((s) => /send the money back/i.test(s)),
      "…it says the money is SENT BACK (the refund path, chosen by the engine)",
    );
    check(
      consequence.some((s) => /not a credit|no next bill/i.test(s)),
      "…and that it is not a credit, because there is no next bill to carry it to (BR-CWP-048)",
    );

    // ── the closing reading ───────────────────────────────────────────────
    const closing = page.locator('[data-testid="closing-reading"]');
    const closingRows = await closing.locator("[data-kv]").all();
    over(closingRows, "CWP-032 CLOSING READING rows", { expected: 3 });
    const closingText = (await closing.innerText()).trim();
    record("the closing reading panel", JSON.stringify(closingText.replace(/\s+/g, " ").slice(0, 180)));
    // ⚠ **HARD RULE 3 — a consumption is never a bare number.** The drawing
    // puts `1,270 gal` beside *Used since 1 Sep*; a cell reading `1270` with the
    // unit only in the label would pass a `toContain("1270")` and be wrong.
    check(
      /\b[\d,]+\s*(gal|kWh|therm|ccf|m³)\b/i.test(closingText),
      "the consumption carries its unit on the cell (hard rule 3)",
    );
    check(/\b154,?310\b/.test(closingText), "the closing reading is the one taken on the move-out day");
    check(
      /meter reader|read by/i.test(closingText),
      "…and it says a person the utility SENT took it, in words rather than a code",
    );

    // ── the query route, on the half the drawing actually draws ───────────
    const queryOpen = await page.locator('[data-query-reading="open"]').count();
    const queryClosed = await page.locator('[data-query-reading="closed"]').count();
    record("query route on the refund bill", queryOpen ? "OPEN" : queryClosed ? "CLOSED" : "absent");
    // ⚠ **THE DRAWING PUTS *Query this reading* ON THIS SCREEN — the $89.80
    // refund — AND THE PRODUCT CANNOT EVER SHOW IT THERE.** `settled` is
    // `path is not None or remainder == 0`; a refund sets its path
    // automatically, so the control is withdrawn before the customer has read
    // the page once. Recorded as a gap so this run stays readable, and filed.
    gaps.known(queryOpen === 1, "the *Query this reading* control the drawing puts on the refund screen", {
      defect: "DEF-CWP-4192",
      why: "an automatic refund is `settled` the instant it is computed, so query_reading_open is false on the very screen P18 draws the control on. The customer is sent to the telephone instead",
    });
    if (queryClosed === 1) {
      const closedSentence = (await page.locator('[data-query-reading="closed"]').innerText()).trim();
      record("what a leaving customer is told instead", JSON.stringify(closedSentence));
      check(
        closedSentence.length > 0,
        "…and the control does not merely vanish: a sentence says why (BR-CWP-056)",
      );
    }

    // ── what the drawing has in the head and the product does not ─────────
    const pdf = await page.getByRole("link", { name: /pdf/i }).count()
      + await page.getByRole("button", { name: /pdf/i }).count();
    gaps.known(pdf > 0, "a ↓ PDF action in the head, as the drawing puts it", {
      defect: "DEF-CWP-4000",
      why: "P18 draws ↓ PDF and Pay beside the title; CWP-032 composes PageHeader with no actions at all, so a leaving customer cannot keep a copy of the last bill they will ever get",
    });
    const pay = await page.getByRole("button", { name: /^pay/i }).count();
    gaps.known(pay > 0, "a Pay action in the head, as the drawing puts it", {
      defect: "DEF-CWP-4000",
      why: "same missing head actions. On a *we owe you* bill a Pay control would be wrong anyway — the drawing shows both together, which is the drawing's own oddity and is recorded in 13-wireframe-delta.md",
    });

    await noInternals(page, "CWP-032 (we owe you)");
    await shot(page, "6a-final-bill-we-owe-you");
  }

  // ═════════════════════════════════════════════════════════════════════════
  // 6b · THE OTHER HALF — the customer who still owes
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 6b · the same screen when the charges exceed the deposit (you owe us) ──");
  await signOut(page);
  await signIn(page, OWING_EMAIL);
  await page.goto(`${PORTAL}/final-bill`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-032"]', { timeout: 20000 });

  const owingNone = await page.locator("[data-final-none]").count();
  check(owingNone === 0, "the second leaving customer's final bill is on the screen too");
  if (owingNone > 0) {
    skip("6b: the fixture's second move-out is not present");
  } else {
    const { lines, total } = await settlingUp(page);
    over(lines, "CWP-032 SETTLING UP lines (you owe us)", { expected: 3 });
    for (const line of lines) record(`  ${line.label}`, line.value);
    record("  TOTAL", `${total.label} ${total.value}`);

    check(/you owe us/i.test(total.label), "charges larger than the deposit read *You owe us*");
    check(money(total.value) > 0, "…and the remainder is positive");

    // ⚠ **THE SAME ARITHMETIC, ON AN ACCOUNT THAT ALSO OWED SOMETHING BEFORE.**
    // The deposit settles *"everything outstanding"* — the PO's own words
    // closing `OQ-158` — so the total includes arrears the panel does not list.
    // `billing_seam.final_bill_for` serves BOTH `service_charges` and `charges`
    // and says in its own docstring that a screen given only one of them *"would
    // either hide the arrears or misname the service charge"*. The screen reads
    // only `service_charges`. Recorded as a gap; filed as DEF-CWP-4191.
    const sum = lines.reduce((acc, line) => acc + money(line.value), 0);
    const stated = money(total.value);
    record("the settling-up arithmetic", `${sum.toFixed(2)} (lines) vs ${stated.toFixed(2)} (stated)`);
    gaps.known(
      Math.abs(sum - stated) < 0.005,
      "the settling-up lines add up to the total when the account ALSO had arrears",
      {
        defect: "DEF-CWP-4191",
        why: `the panel lists ${lines.map((l) => l.value).join(" + ")} = ${sum.toFixed(2)} and states ${total.value}; the gap is what the account already owed, which no line names`,
      },
    );

    const queryOpen = await page.locator('[data-query-reading="open"]').count();
    record("query route on the owed bill", queryOpen ? "OPEN" : "closed/absent");
    check(
      queryOpen === 1,
      "*Query this reading* IS drawn while a staff choice is still outstanding — the only state that shows it",
    );
    if (queryOpen === 1) {
      const link = page.locator('[data-query-reading="open"] a');
      const href = await link.getAttribute("href").catch(() => null);
      record("where *Query this reading* goes", href ?? "(not a link)");
      // A control that points nowhere is worse than one that is held
      // (DEF-CWP-3962's own lesson, one screen over). The destination must be a
      // real bill number, not `/bills//dispute`.
      check(
        !!href && /\/bills\/[^/]+\/dispute$/.test(href),
        "…and it opens the dispute screen for a REAL bill number, not /bills//dispute",
      );
    }

    await noInternals(page, "CWP-032 (you owe us)");
    await shot(page, "6b-final-bill-you-owe-us");
  }

  // ═════════════════════════════════════════════════════════════════════════
  // 7 · A VISIT IS BOOKED
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 7 · a visit is booked at the property ──");
  await page.goto(`${PORTAL}/requests/visits`, { waitUntil: "networkidle" });
  const visitsScreen = await page.locator("[data-screen]").getAttribute("data-screen").catch(() => null);
  record("what /requests/visits opens", visitsScreen ?? "(no screen element)");
  gaps.known(visitsScreen === "CWP-067", "the drawing's address /requests/visits opens *A visit is booked*", {
    defect: "DEF-CWP-3988",
    why: "CWP-067 is unbuilt and BLOCKED — OQ-249 (is field work a module of its own?) is OPEN, Work half only, and the PO put it at release R5",
  });
  // ⚠ **AND THIS ONE IS DIFFERENT FROM CWP-035 IN THE WAY THAT MATTERS.** The
  // drawing's own caption says so: *"Nothing in the product publishes a booked
  // visit to a customer today. The job record exists; the field-work module's
  // scope does not."* CWP-035 is unbuilt and UNBLOCKED; CWP-067 is unbuilt and
  // waiting on a ruling nobody has asked for again (law 13).
  gaps.known(false, "a booked visit published to the customer whose property it is", {
    defect: "DEF-CWP-3988",
    why: "the WorkOrder row exists in apps/metering/connections.py; what does not exist is any portal read of it, and OQ-249 decides where that read may live",
  });
  await shot(page, "7-visits");

  // ═════════════════════════════════════════════════════════════════════════
  // 8 · nothing internal on any screen this wave owns
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 8 · no database id and no internal code (B14 rule 31 / 32) ──");
  await page.goto(`${PORTAL}/readings`, { waitUntil: "networkidle" });
  await noInternals(page, "CWP-034");

  // ── the report ───────────────────────────────────────────────────────────
  console.log("\n──────────────────────────────────────────────────────────────");
  console.log("FIGURES THIS RUN PRINTED");
  for (const f of figures) console.log(`   ${f}`);
  if (skipped.length) {
    console.log("\nSKIPPED");
    for (const s of skipped) console.log(`   ~ ${s}`);
  }
  console.log("");
  timings.report?.();
  console.log(`   screenshots in ${OUT}`);

  await browser.close();
  process.exit(gaps.report(failures));
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
