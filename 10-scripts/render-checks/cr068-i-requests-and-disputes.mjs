/**
 * RENDERED-OUTPUT CHECK — CR-068 wave I, "Requests, disputes and a question",
 * in a real browser. Screens `CWP-046` (/requests), `CWP-052`
 * (/stop-or-restart), `CWP-051` (/requests/:reference), `CWP-055`
 * (/bills/:number/dispute) and `CWP-054` (/ask-a-question).
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: no gate in this repository looks at
 * rendered output, and nine defects in one day were found this way and by
 * nothing else. PO ruling 2026-09-03: *"ensure you do web walkthorugh before
 * you sign off the user story or build"*. The execution plan named this file
 * at wave I's task `I4` and it did not exist until today.
 *
 * ⚠ **AND THIS WAVE'S SUBJECT IS TWO ABSENCES AND ONE ARITHMETIC, WHICH IS
 * WHY A UNIT TEST WAS NEVER GOING TO BE ENOUGH.**
 *   · `BR-CWP-078` is satisfied by a clerk's *"route to Tuesday crew"* being
 *     NOWHERE on `CWP-051` — a negative over a whole rendered page;
 *   · `US-CWP-064`'s deferral is satisfied by there being **no `input[type=
 *     file]` in the DOM** of `CWP-054`, which is a claim about the document
 *     and not about a payload;
 *   · `BR-CWP-081` is satisfied only if the verdict **FLIPS** — a screen that
 *     always says *stopping is cheaper* passes every single-case test there
 *     is, and `US-CWP-062` §7 names that exact failure.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   10-scripts/proof-db.sh clone cwpi --export     # then export what it prints
 *   export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false
 *   python3 06-backend/manage.py seed_portal_demo
 *   python3 10-scripts/render-checks/cr068-i-fixture.py
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8145 --noreload &
 *   (cd 07-frontend && ./node_modules/.bin/vite build && \
 *      PORT=4345 API_PROXY_TARGET=http://127.0.0.1:8145 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4345 node 10-scripts/render-checks/cr068-i-requests-and-disputes.mjs
 *
 * ⚠ **BUILD THE BUNDLE FIRST.** A stale `dist/` means every assertion here
 * passes or fails about a build nobody is shipping.
 * ⚠ **RUN THE FIXTURE.** `seed_portal_demo` alone leaves FOUR of these five
 * screens in an empty branch and the fifth saying it cannot work its own
 * comparison out — see `cr068-i-fixture.py`'s docstring, which measures it.
 * A run without the fixture reports these screens clean and proves nothing.
 * ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** A mid-run reseed
 * looks exactly like a broken screen.
 *
 * ── WHAT IT CLICKS (the wave I demo script, 10-execution-plan.md) ─────────
 *   1  `/requests` — SIX cards read from the tenant's own categories, three
 *      live and three held each carrying a reason of five or six words; the
 *      open-requests table with its reference, its status chip and its row
 *      icon, and the reference opening `CWP-051`.
 *   2  Moving out (`CWP-048`) — NOT BUILT. A known gap, and the register row
 *      it carries is not the one the execution plan names (see below).
 *   3  The row a clerk sees carries channel **customer portal**, and the
 *      portal edge serves NO approve, refuse or close route (`BR-CWP-075`).
 *   4  `/stop-or-restart` — the comparison, driven THREE times so the verdict
 *      is proved to FLIP: five months `$92.50` against `$335.00` (stopping),
 *      twelve months `$222.00` (still stopping, and `DEF-CWP-3608` is why that
 *      case is here), nineteen months `$351.50` (closing). Every figure is
 *      read off the screen and the arithmetic is checked against the monthly
 *      charge the same screen printed.
 *   5  `/requests/{reference}` — the six-step ladder, *Open for* computed, the
 *      customer's note PRESENT and the clerk's routing note ABSENT from the
 *      whole page and from the fetched body, and Withdraw offered.
 *   6  Documents we need (`CWP-049`) — NOT BUILT, blocked, and its own drawing
 *      says so. A known gap.
 *   7  `/bills/{number}/dispute` — the two-cell stepper, the consequence box,
 *      the query sent, and then the API asked whether `total` moved. It did
 *      not, and a SECOND undisputed bill is still there — hard rule 4.
 *   8  `/ask-a-question` — the topic and bill controls, the three published
 *      answers, two DIFFERENT phone numbers, and no file input anywhere.
 *   9  B14 rule 31/32 across all five, and the regional date format.
 *
 * ⚠ **WHAT IT REFUSES TO CLAIM, AND HOW.** Two of wave I's seven stories are
 * not built and three more things the drawings ask for are not in the product.
 * All of them are recorded through `lib/knownGaps.mjs` as **known gaps with
 * their register ids** — never as silent skips and never as failures.
 * **A CHECK THAT IS RED BY DESIGN IS A CHECK NOBODY READS**: `G103` sat red
 * for 165 commits doing exactly that. A gap here goes red in BOTH directions —
 * still missing is counted and printed; PRESENT is a failure naming the row to
 * delete — so nothing is being silenced. The counts print on a pass too,
 * because `0 failures, 5 known gaps` must never look like `0 failures, 0
 * known gaps`.
 *
 * ⚠ **ONE OF THOSE GAPS DOES NOT CARRY THE ID THE EXECUTION PLAN GIVES IT.**
 * Wave I's row says `CWP-048` is *"blocked on `OQ-1392`"*. `OQ-1392` was
 * CLOSED on 2026-09-04 — the PO ruled option (a), *"ask only"* — and
 * `BR-CWP-082` is CONFIRMED in the module's own rule table. So the screen is
 * not blocked on anything; it is simply unbuilt, and the plan's prose is the
 * stale body `CLAUDE.md`'s prime directive warns about (*"the status column
 * decides, and a body that contradicts it is stale until proved otherwise"*).
 * The gap below names `DEF-CWP-3988`, which is the row that actually records
 * the ten unbuilt screens, and `DEF-CWP-4200` records the stale claim.
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
 * Where chromium actually is.
 *
 * ⚠ **`executablePath()` RETURNS A PATH, NOT A BROWSER**, and it is computed
 * from the version playwright was built against rather than from what is
 * installed — so it can answer a path that does not exist without throwing.
 * The path is TESTED here rather than trusted (hard-won law 7's second shape,
 * a check structurally incapable of failing). Same eight lines as `cr068-h`.
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4345";
const TENANT = process.env.SMOKE_TENANT ?? "pine-hill";
const EMAIL = process.env.SMOKE_EMAIL ?? "i-requests@example.test";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "Elm-Street-1408";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr068-i";
const VIEWPORT = { width: 1440, height: 1000 };
const PORTAL = `${BASE}/${TENANT}/portal`;
const API = `${BASE}/api/${TENANT}/portal`;

/** `cr068-i-fixture.py`'s own constants — the two files must agree. */
const QUERIED_BILL = process.env.SMOKE_BILL ?? "BL-I-2608-0141";
const QUERIED_TOTAL = "142.18";
const OTHER_BILL = "BL-I-2609-0152";
const ROUTING_NOTE = "route to Tuesday crew, low priority";
const CUSTOMER_NOTE = "We need proof of address and your landlord's consent.";

/**
 * The wave I demo script's own comparison, and the reason there are THREE
 * cases rather than one.
 *
 * ⚠ **A VERDICT THAT NEVER FLIPS IS NOT A VERDICT** (`US-CWP-062` §7: *"a
 * screen that always says stopping is cheaper is wrong for a long absence"*).
 * One case proves nothing — the screen could be printing a constant. The
 * middle case is here because the demo script said TWELVE months crossed the
 * line until 2026-09-03, when `DEF-CWP-3608` measured it and it does not:
 * `12 × $18.50 = $222.00` is well under `$335.00`.
 */
const MONTHLY = "18.50";
const CLOSING = "335.00";
const CASES = [
  { months: 5, stop: "2026-11-01", start: "2027-04-01", cost: "92.50", verdict: "stopping" },
  { months: 12, stop: "2026-11-01", start: "2027-11-01", cost: "222.00", verdict: "stopping" },
  { months: 19, stop: "2026-11-01", start: "2028-06-01", cost: "351.50", verdict: "closing" },
];

mkdirSync(OUT, { recursive: true });

const failures = [];
const skipped = [];
const gaps = new Gaps();
/** Every figure this run READ OFF THE SCREEN, printed together at the end. */
const figures = [];

function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

/**
 * A step this run could not exercise, named out loud.
 *
 * ⚠ **NOT A PASS, AND NOT COUNTED AS ONE.** Hard-won law 7's fifth shape is a
 * check reporting zero over a scope it silently excludes — *"a declared blind
 * spot with no NUMBER attached is indistinguishable from an empty one"*.
 */
function skip(message) {
  console.log(`   ⏭ SKIPPED — ${message}`);
  skipped.push(message);
}

function record(label, value) {
  figures.push(`${label}: ${value}`);
  console.log(`   · ${label} = ${value}`);
}

/**
 * ⚠ **THE ONE HELPER THIS SCRIPT WOULD BE WORTHLESS WITHOUT.**
 *
 * `[].every(...)` is `true`, so *"every card carries a reason"* PASSES over a
 * page with no cards on it — and a page with nothing on it is precisely the
 * state four of these five screens are in before this wave's fixture runs.
 * So a claim about "every X" is made in TWO parts, and the first part is that
 * there is an X at all.
 */
function over(items, where, { min = 1, expected = null } = {}) {
  const n = items.length;
  if (expected !== null) {
    check(
      n === expected,
      `${where}: ${n} drawn (expected ${expected}) — nothing below is vacuous`,
    );
  } else {
    check(n >= min, `${where}: ${n} drawn (need at least ${min}) — nothing below is vacuous`);
  }
  return n > 0;
}

/** Money as digits, so `$92.50` and `92.50` compare equal. */
const moneyIn = (text) => (text ?? "").replace(/[^0-9.]/g, "");
const hasMoney = (text, amount) => (text ?? "").replace(/,/g, "").includes(amount);

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
 * A raw machine date on a customer's screen.
 *
 * ⚠ **THE TENANT'S OWN SETTING IS `MM/DD/YYYY`** and `usePortalDate` has
 * existed for days — `DEF-CWP-4138` moved wave M's five screens onto it and
 * `DEF-CWP-4178` moved wave L's four. This counts what is left, so the number
 * is a measurement rather than an impression.
 */
const ISO_DATE = /\b\d{4}-\d{2}-\d{2}\b/g;
/**
 * ⚠ **ONE PIECE OF TEXT ON THESE SCREENS IS NOT THE SCREEN'S TO FORMAT, AND
 * COUNTING IT HERE WOULD BLAME THE WRONG FILE.** The clerk's routing sentence
 * is STORED prose written at the moment a query was sent; the dates inside it
 * are part of `DEF-CWP-4198` and are recorded as a known gap on `CWP-046`
 * above. Everything else is a date the screen chose how to draw, which is
 * `DEF-CWP-4204`'s subject. The two are separated so a reader of this run can
 * tell which file to open — and the count of what was set aside is PRINTED,
 * because a declared blind spot with no number attached is indistinguishable
 * from an empty one (law 7's fifth shape).
 */
const STORED_PROSE = /Queried through the customer portal[^\n]*/g;
async function machineDates(page, where) {
  const raw = await page.locator("body").innerText();
  const stored = raw.match(STORED_PROSE) ?? [];
  const text = raw.replace(STORED_PROSE, "");
  const hits = text.match(ISO_DATE) ?? [];
  const setAside = (stored.join(" ").match(ISO_DATE) ?? []).length;
  if (hits.length || setAside) {
    record(
      `${where} raw ISO dates`,
      `${hits.length} the screen drew${setAside ? `, ${setAside} more inside the stored query sentence (DEF-CWP-4198, not this screen's to format)` : ""}` +
        (hits.length ? ` — ${hits.slice(0, 4).join(", ")}` : ""),
    );
  }
  return hits;
}

async function signIn(page) {
  await page.goto(`${PORTAL}/sign-in`, { waitUntil: "networkidle" });
  await page.fill("#portal-email", EMAIL);
  await page.fill("#portal-password", PASSWORD);
  await page.getByRole("button", { name: /sign in/i }).click();
  await page.waitForSelector('[data-portal-frame="shell"]', { timeout: 20000 });
}

/** Ask the product's own API, through the session the browser is holding. */
async function api(page, path) {
  return page.evaluate(async (url) => {
    const answer = await fetch(url, { credentials: "include" });
    return { status: answer.status, body: await answer.text() };
  }, `${API}/${path}`);
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT, acceptDownloads: true });
  const timings = attachTimings(context);
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });
  /**
   * ⚠ **EVERY READ THE PAGE ITSELF WAS REFUSED, REMEMBERED BY PATH.**
   *
   * The portal throttles its reads per window, and this run opens five screens
   * and sends three writes inside a minute. When `GET /bills` came back `429`,
   * `CWP-054`'s *Which bill* control drew one option and its suggestions panel
   * vanished — **with nothing on the screen saying anything had gone wrong** —
   * and a check that asked only *"what did the screen draw"* reported the
   * product broken. A later check that asked the API directly reported the
   * screen broken instead, because by then the window had reopened.
   * **Neither was true.** So the run records what the BROWSER was answered, and
   * a control that is empty because its read was refused is a SKIP naming the
   * status — not a pass, and not a failure the next reader has to re-diagnose.
   */
  const refused = new Map();
  page.on("response", (r) => {
    if (r.status() === 429) {
      const path = new URL(r.url()).pathname;
      refused.set(path, (refused.get(path) ?? 0) + 1);
    }
  });
  const wasThrottled = (fragment) =>
    [...refused.keys()].some((path) => path.includes(fragment));
  console.log(`cr068-i: ${BASE} tenant=${TENANT} as ${EMAIL} ${VIEWPORT.width}x${VIEWPORT.height}`);

  await signIn(page);
  let allDates = [];

  // ═════ 1 · what do you need — six cards, and three of them are held ══════
  console.log("\n── 1 · CWP-046, the six cards and what is already open ──");
  await page.goto(`${PORTAL}/requests`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-046"]', { timeout: 20000 });
  await page.screenshot({ path: join(OUT, "1-cwp-046-requests.png"), fullPage: true });

  // ⚠ **THE CARDS ARE COUNTED BEFORE ANYTHING IS ASSERTED ABOUT THEM.** The
  // hub renders its heading whether or not the tenant published any category,
  // so a claim about "every card" would pass on an empty grid.
  const errands = await page.locator("[data-errand]").all();
  over(errands, "CWP-046 errand cards", { min: 6 });
  const codes = [];
  for (const one of errands) codes.push(await one.getAttribute("data-errand"));
  record("CWP-046 errand cards drawn", `${errands.length} — ${codes.join(", ")}`);

  // Three lead somewhere, three are held. The SERVER decides which
  // (`ERRAND_HELD_UNTIL`), so this asserts the split rather than the names.
  const live = await page.locator('[data-screen="CWP-046"] a[href*="/portal/"]').all();
  const held = await page.locator('[data-screen="CWP-046"] button[disabled]').all();
  record("CWP-046 live doors / held controls", `${live.length} / ${held.length}`);
  check(held.length >= 3, `three cards are HELD, not dead links (${held.length} disabled)`);
  if (over(held, "CWP-046 held controls", { min: 1 })) {
    // ⚠ **B14 rule 33 — a refusal is FIVE OR SIX WORDS**, and `BR-CWP-056`
    // says a held control carries its reason where a person can read it.
    let withReason = 0;
    let longest = "";
    for (const one of held) {
      const title = (await one.getAttribute("title")) ?? "";
      const near = await one.evaluate((el) => el.parentElement?.innerText ?? "");
      const reason = title || near;
      if (reason.trim() !== "") withReason += 1;
      if (reason.split(/\s+/).length > longest.split(/\s+/).length) longest = reason.trim();
    }
    check(
      withReason === held.length,
      `every held card carries a reason a person can read (${withReason} of ${held.length})`,
    );
    record("CWP-046 longest refusal", `"${longest}" (${longest.split(/\s+/).length} words)`);
    check(
      longest.split(/\s+/).filter(Boolean).length <= 8,
      `…and the longest is short enough to read (B14 rule 33): "${longest}"`,
    );
  }

  // The open-requests table. THE FIXTURE PUT ONE REQUEST HERE ON PURPOSE —
  // without it this whole block is the empty-state sentence and every
  // assertion below would be vacuous.
  const emptyPanel = await page.locator("[data-requests-empty]").count();
  check(emptyPanel === 0, "the OPEN REQUESTS panel is a TABLE, not the nothing-here sentence");
  const refCells = await page.locator("[data-reference]").all();
  const haveRows = over(refCells, "CWP-046 open request rows", { min: 1 });
  let reference = null;
  if (haveRows) {
    // ⚠ **THE MOVE-OUT ROW BY NAME, NEVER `.first()`.** This walkthrough SENDS
    // a bill query at step 7, so on any second run the list holds two rows and
    // the newest is the query. A `.first()` here silently retargeted steps 3
    // and 5 onto a request that has no clerk note and no documents — which
    // made *"the routing note is absent"* pass over a request that never had
    // one, the vacuous-pass shape this file's `over()` exists to stop.
    const links = await page.locator("[data-request-link]").all();
    for (const one of links) {
      const rowText = await one.evaluate((el) => el.closest("tr")?.innerText ?? "");
      if (/Moving out on 17 September/i.test(rowText)) {
        reference = await one.getAttribute("data-request-link");
        break;
      }
    }
    check(
      reference !== null,
      `the MOVE-OUT request the fixture planted is in the list (${links.length} row(s) drawn)`,
    );
    record("CWP-046 the move-out reference", reference ?? "(not found)");
    check(
      /^SR-\d{2}-\d{4}$/.test(reference ?? ""),
      `the visible handle is the SR- number a customer reads out, never a row id (B14 rule 31): ${reference}`,
    );
    const rowText = await page
      .locator(`[data-request-link="${reference}"]`)
      .evaluate((el) => el.closest("tr")?.innerText ?? "")
      .catch(() => "");
    record("CWP-046 the row", JSON.stringify(rowText.replace(/\s+/g, " ").trim()));
    // `US-CWP-060` TC-4 — waiting on documents OVERRIDES the state, because it
    // is the one thing the customer can act on.
    check(
      /document/i.test(rowText),
      `the status chip says what WE are waiting for, not an internal state: "${rowText.replace(/\s+/g, " ").trim()}"`,
    );
  }
  await noInternals(page, "CWP-046");
  allDates = allDates.concat(await machineDates(page, "CWP-046"));

  // ═════ 2 · moving out — NOT BUILT ════════════════════════════════════════
  console.log("\n── 2 · CWP-048, moving out ──");
  await page.goto(`${PORTAL}/move-out`, { waitUntil: "networkidle" });
  const moveOutBody = (await page.locator("body").innerText()).trim();
  gaps.known(
    moveOutBody.length > 0 && !/not built|nothing here/i.test(moveOutBody),
    "a screen for MOVING OUT (CWP-048), with its danger-tier commit and the distinction panel",
    {
      defect: "DEF-CWP-3988",
      why:
        "one of the ten screens the drawing describes and the product does not serve; the errand " +
        "card on CWP-046 holds honestly today and the server names CWP-048 as what releases it. " +
        "⚠ the execution plan calls it 'blocked on OQ-1392' and that is STALE — OQ-1392 closed " +
        "2026-09-04 with 'ask only' and BR-CWP-082 is CONFIRMED, so nothing blocks it (DEF-CWP-4200)",
    },
  );

  // ═════ 3 · the row a clerk sees, and the doors that do not exist ═════════
  console.log("\n── 3 · the channel on the row, and what the portal edge refuses ──");
  if (reference) {
    const detail = await api(page, `requests/${encodeURIComponent(reference)}`);
    check(detail.status === 200, `GET requests/${reference} answers 200 (got ${detail.status})`);
    // `BR-CWP-076` — the row is identifiable as the portal's on the worklist.
    // Asserted through the STAFF-visible fact rather than the portal payload,
    // because the portal deliberately does not serve `channel`.
    const hub = await api(page, "requests");
    const listed = JSON.parse(hub.body).open_requests ?? [];
    check(
      listed.some((row) => row.reference === reference),
      `the request is in THIS LOGIN's own list — the phone-based link works (${listed.length} row(s))`,
    );
    // `BR-CWP-075` — exactly four customer transitions, and approve/refuse are
    // NOT among them. Asserted by asking the edge for them.
    for (const door of ["approve", "refuse", "close"]) {
      const tried = await page.evaluate(
        async ([url]) => {
          const answer = await fetch(url, { method: "POST", credentials: "include" });
          return answer.status;
        },
        [`${API}/requests/${encodeURIComponent(reference)}/${door}`],
      );
      check(
        tried === 404 || tried === 405,
        `the portal edge serves NO ${door} route (${tried}) — BR-CWP-075`,
      );
    }
  } else {
    skip("the channel and transition checks — no request reference was on CWP-046");
  }

  // ═════ 4 · stop or restart — and the verdict has to FLIP ═════════════════
  console.log("\n── 4 · CWP-052, both figures, and the cheaper option NAMED ──");
  await page.goto(`${PORTAL}/stop-or-restart`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-052"]', { timeout: 20000 });

  const unavailable = await page.locator("[data-compare-unavailable]").count();
  let verdicts = [];
  for (const one of CASES) {
    await page.fill("#stop_from", one.stop);
    await page.fill("#start_again", one.start);
    // The comparison is re-asked of the SERVER on every change; wait for it.
    await page.waitForTimeout(1200);
    const panel = await page
      .locator('[data-testid="stop-compare"], [data-testid="stop-compare-waiting"]')
      .first()
      .innerText()
      .catch(() => "");
    const verdict = await page
      .locator("[data-verdict]")
      .first()
      .getAttribute("data-verdict")
      .catch(() => null);
    verdicts.push(verdict);
    record(
      `CWP-052 ${one.months} months`,
      `verdict=${verdict ?? "(none)"} · panel=${JSON.stringify(panel.replace(/\s+/g, " ").trim().slice(0, 150))}`,
    );
    // ⚠ **BOTH FIGURES, ON THE SCREEN** (`BR-CWP-081`). Not one and a verdict.
    check(hasMoney(panel, one.cost), `…the cost of STOPPING is $${one.cost} on the screen`);
    check(hasMoney(panel, CLOSING), `…the cost of CLOSING is $${CLOSING} on the screen`);
    check(
      verdict === one.verdict,
      `…and the screen NAMES ${one.verdict} as cheaper (it said ${verdict ?? "nothing"})`,
    );
    // The arithmetic is checked against the monthly figure the SAME screen
    // printed, so this cannot pass on a constant the fixture happened to plant.
    const screen = await page.locator('[data-screen="CWP-052"]').innerText();
    const expected = (Number(MONTHLY) * one.months).toFixed(2);
    check(
      expected === one.cost && hasMoney(screen, MONTHLY),
      `…${one.months} × $${MONTHLY} = $${expected}, and $${MONTHLY} a month is printed on the screen`,
    );
  }
  // ⚠ **THE FLIP IS THE ASSERTION.** Three identical answers would satisfy
  // every check above and still be the constant `US-CWP-062` §7 forbids.
  check(
    new Set(verdicts.filter(Boolean)).size >= 2,
    `the verdict FLIPS across the three windows (${verdicts.join(" → ")}) — not a constant`,
  );
  check(unavailable === 0, "the comparison is DRAWN, not the we-cannot-work-it-out sentence");

  // `BR-CWP-080` — the most expensive misunderstanding in the product.
  const stopText = await page.locator('[data-screen="CWP-052"]').innerText();
  const staysOpen = await page.locator('[data-consequence-code="stays_open"]').count();
  const chargesRun = await page.locator('[data-consequence-code="charges_run"]').count();
  check(staysOpen > 0, "the consequence box says THE ACCOUNT STAYS OPEN (BR-CWP-080)");
  check(chargesRun > 0, "…and that standing charges keep running");
  // B14 rule 11 — a form that writes service state shows a what-this-will-do
  // box BEFORE its commit button. Asserted by position, not by presence.
  const boxBeforeCommit = await page.evaluate(() => {
    const box = document.querySelector('[data-consequence-code="stays_open"]');
    const buttons = [...document.querySelectorAll("button")];
    const commit = buttons.find((b) => /request|send|ask/i.test(b.textContent ?? ""));
    if (!box || !commit) return null;
    return box.compareDocumentPosition(commit) & Node.DOCUMENT_POSITION_FOLLOWING ? true : false;
  });
  check(
    boxBeforeCommit === true,
    "the WHAT THIS WILL DO box comes BEFORE the commit button (r10 rule 11)",
  );
  await page.screenshot({ path: join(OUT, "4-cwp-052-stop-or-restart.png"), fullPage: true });
  await noInternals(page, "CWP-052");
  allDates = allDates.concat(await machineDates(page, "CWP-052"));
  record("CWP-052 screen money", JSON.stringify((stopText.match(/\$[\d,]+\.\d{2}/g) ?? []).join(" ")));

  // ═════ 5 · track your request — and the note nobody may see ══════════════
  console.log("\n── 5 · CWP-051, the ladder, and the clerk's note that must not show ──");
  if (reference) {
    await page.goto(`${PORTAL}/requests/${encodeURIComponent(reference)}`, {
      waitUntil: "networkidle",
    });
    await page.waitForSelector('[data-screen="CWP-051"]', { timeout: 20000 });
    await page.screenshot({ path: join(OUT, "5-cwp-051-track.png"), fullPage: true });

    const missing = await page.locator('[data-testid="request-missing"]').count();
    check(missing === 0, "the request OPENS — this is the real screen, not the not-found branch");

    const steps = await page.locator('[data-screen="CWP-051"] li, [data-screen="CWP-051"] ol > *').all();
    const stepText = await page.locator('[data-testid="request-progress"]').innerText();
    record("CWP-051 progress panel", JSON.stringify(stepText.replace(/\s+/g, " ").trim().slice(0, 220)));
    check(
      (stepText.match(/\n/g) ?? []).length >= 5,
      "the progress ladder draws its six steps, not a subset",
    );
    over(steps, "CWP-051 list items", { min: 1 });

    // ⚠ **THE ASSERTION THE SCREEN EXISTS FOR** (`BR-CWP-078`, `US-CWP-063`
    // TC-2). Over the WHOLE page AND the whole fetched body — a field that is
    // served and merely not drawn is still served.
    const pageText = await page.locator("body").innerText();
    check(!pageText.includes(ROUTING_NOTE), `the clerk's routing note is NOT on the screen`);
    check(!/Tuesday crew/i.test(pageText), "…and no fragment of it is either");
    const body = await api(page, `requests/${encodeURIComponent(reference)}`);
    check(
      !body.body.includes(ROUTING_NOTE) && !/Tuesday crew/i.test(body.body),
      "…and it is not in the response body the browser was handed",
    );
    // ⚠ **AND THE FILTER IS NOT VACUOUS**: the customer's OWN note must be
    // there. Without this the check above passes over an empty timeline.
    check(
      pageText.includes(CUSTOMER_NOTE) || body.body.includes(CUSTOMER_NOTE),
      "…while the note written FOR the customer IS present — so the filter is not empty",
    );

    const openFor = await page.locator('[data-detail="open_for"]').innerText().catch(() => "");
    record("CWP-051 open for", JSON.stringify(openFor.trim()));
    check(openFor.trim() !== "", "*Open for* is computed and shown (US-CWP-063 §4)");
    // ⚠ **ABSENT AND EMPTY ARE DIFFERENT ANSWERS AND THIS ASKS WHICH.**
    // `BR-CWP-093` and the screen's own docstring: *"Waiting on with nothing
    // beside it reads as waiting on nothing"*, so a null row must be OMITTED.
    // A single `.innerText().catch(() => "")` cannot tell the two apart — it
    // returns "" for both — which is law 7's *"a check whose output cannot
    // distinguish pass from fail"*.
    const waitingCount = await page.locator('[data-detail="waiting_on"]').count();
    const waiting =
      waitingCount > 0 ? await page.locator('[data-detail="waiting_on"]').innerText() : null;
    record(
      "CWP-051 waiting on",
      waitingCount === 0 ? "(row ABSENT)" : JSON.stringify(waiting.trim()),
    );
    check(
      waitingCount === 0 || waiting.trim() !== "",
      "*Waiting on* is either absent or says something — never a drawn row with a blank beside it (BR-CWP-093)",
    );

    // `BR-CWP-079` — withdrawable until approved, and it is NOT the danger
    // tier, because withdrawing destroys nothing.
    const withdraw = page.locator('[data-action="withdraw"]');
    const canWithdraw = (await withdraw.count()) > 0;
    check(canWithdraw, "WITHDRAW is offered while the request is not yet approved (BR-CWP-079)");
    if (canWithdraw) {
      const tier = await withdraw.evaluate((el) => getComputedStyle(el).backgroundColor);
      record("CWP-051 withdraw button colour", tier);
      const danger = await page.locator("[class*='danger']").count();
      check(
        !(await withdraw.evaluate((el) => el.className.includes("danger"))),
        `…and it is NOT the danger tier (r10 rule 6): className has no danger (page has ${danger} danger nodes)`,
      );
    }
    await noInternals(page, "CWP-051");
    allDates = allDates.concat(await machineDates(page, "CWP-051"));
  } else {
    skip("CWP-051 entirely — there was no reference on CWP-046 to open");
  }

  // ═════ 6 · documents we need — NOT BUILT ═════════════════════════════════
  console.log("\n── 6 · CWP-049, documents we need from you ──");
  gaps.known(false, "a screen listing the documents we still need (CWP-049)", {
    defect: "DEF-CWP-3988",
    why:
      "nothing points at it and it cannot be built as drawn: the portal accepts NO upload, which " +
      "is a signed deferral, and its own wireframe carries a BLOCKED stamp saying so. The " +
      "checklist behind it is real — CWP-046's chip reads 'we need two documents' off it",
  });

  // ═════ 7 · dispute a bill — and the bill does not move ═══════════════════
  console.log("\n── 7 · CWP-055, a query that changes no row ──");
  const before = await api(page, `bills/${encodeURIComponent(QUERIED_BILL)}`);
  check(before.status === 200, `the bill ${QUERIED_BILL} exists to be queried (${before.status})`);
  const totalBefore = (JSON.parse(before.body || "{}").total ?? "").toString();
  record("bill total BEFORE the query", totalBefore || "(none)");

  await page.goto(`${PORTAL}/bills/${encodeURIComponent(QUERIED_BILL)}/dispute`, {
    waitUntil: "networkidle",
  });
  await page.waitForSelector('[data-screen="CWP-055"]', { timeout: 20000 });
  await page.screenshot({ path: join(OUT, "7-cwp-055-dispute.png"), fullPage: true });

  const stepper = await page.locator('[data-screen="CWP-055"] ol, [data-screen="CWP-055"] nav').count();
  record("CWP-055 stepper elements", `${stepper}`);
  const consequence = await page
    .locator('[data-screen="CWP-055"]')
    .innerText();
  check(
    /does not change|still due/i.test(consequence),
    "the consequence box says the bill itself does not change and the rest is still due",
  );
  // ⚠ **THE DRAWING PROMISES A COLLECTION HOLD AND THE PRODUCT CANNOT KEEP IT**
  // — ruled on 2026-09-05, `OQ-CWP-1682`. The screen ships saying only what the
  // code does, and a test asserts no catalogue promises a hold. So this is a
  // gap against the DRAWING, recorded, and it goes red the day somebody adds
  // the sentence back without the behaviour behind it.
  gaps.known(
    /hold collection|no late fee/i.test(consequence),
    "the WHAT THIS WILL DO box promises 'we hold collection on $142.18 · no late fee while we look' (wireframe CWP-055)",
    {
      defect: "OQ-CWP-1682",
      why:
        "nothing in this product records a DISPUTED AMOUNT — late_fee.ageable_portion raises " +
        "NotImplementedError('OQ-420') rather than choosing between two fallbacks $137.20 apart — " +
        "so the full amount keeps ageing and the minimum late fee applies on schedule. Printing " +
        "the drawing's sentence would be a promise on a customer's money with nothing behind it",
    },
  );

  // Fill it in and send it, which is the only way to prove the row does not move.
  // ⚠ **`selectOption`, NOT `fill` — *What are you questioning* IS A `<select>`
  // NOW** (CR-085 (c); the drawing's five real reasons, chosen from a list
  // rather than composed in an empty box). `page.fill` on a `<select>` throws
  // *"Element is not an <input>, <textarea> or [contenteditable] element"* and
  // takes the rest of this block down with it, so the line is changed here in
  // the same commit as the screen — a walkthrough that cannot get past its own
  // first field proves nothing about the five screens after it.
  await page.selectOption("#dispute-what", { label: "I think the meter reading is wrong" });
  await page.fill("#dispute-reason", "The house was empty for two weeks");
  await page.getByRole("button", { name: /check|next|continue/i }).first().click();
  await page.waitForTimeout(800);
  const sendBtn = page.getByRole("button", { name: /send/i }).first();
  if (await sendBtn.count()) {
    await sendBtn.click();
    await page.waitForTimeout(1500);
  }
  const sent = await page.locator('[data-testid="dispute-sent"]').count();
  check(sent > 0, "the query was ACCEPTED and the screen confirms it with a reference");
  if (sent > 0) {
    const ref = await page
      .locator('[data-testid="dispute-sent"] [data-reference]')
      .getAttribute("data-reference")
      .catch(() => null);
    record("CWP-055 query reference", ref ?? "(none)");
  }

  // ⚠ **AND A SECOND QUERY ON THE SAME BILL IS REFUSED BY NAME**
  // (`US-CWP-065` TC-9). This is here because the walkthrough MET it by
  // accident on its second run — the first draft cleared nothing, hit the 409
  // and reported a failure over the product behaving correctly. The refusal is
  // real and worth proving, so it is now proved deliberately, in the same run
  // as the write it follows.
  const second = await page.evaluate(
    async ([url]) => {
      const answer = await fetch(url, {
        method: "POST",
        credentials: "include",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ what: "the same thing again", reason: "the same reason again" }),
      });
      return { status: answer.status, body: await answer.text() };
    },
    [`${API}/bills/${encodeURIComponent(QUERIED_BILL)}/dispute`],
  );
  record(
    "CWP-055 a SECOND query on the same bill",
    `HTTP ${second.status} — ${second.body.slice(0, 160)}`,
  );
  check(
    second.status === 409,
    `a second query on ${QUERIED_BILL} is REFUSED (${second.status}) — one open query per bill`,
  );
  // ⚠ **A REFUSAL THAT SAYS NOTHING IS THE FAULT, SO THE BODY IS PRINTED AND
  // NOT MERELY MATCHED.** The first draft matched /already/ and went red on an
  // HTTP 500 — which was a regression this lane had just introduced two files
  // away, and the check reported it as "the refusal does not say so by name".
  // True, and useless. The status is now asserted separately from the wording,
  // and the body is in the run output either way.
  check(
    /alreadyOpen|already/i.test(second.body),
    `…and the refusal names the reason rather than failing anonymously: ${second.body.slice(0, 120)}`,
  );

  // ⚠ **HARD RULE 4, ASKED OF THE PRODUCT RATHER THAN ASSUMED.**
  const after = await api(page, `bills/${encodeURIComponent(QUERIED_BILL)}`);
  const totalAfter = (JSON.parse(after.body || "{}").total ?? "").toString();
  record("bill total AFTER the query", totalAfter || "(none)");
  check(
    totalBefore === totalAfter && moneyIn(totalAfter).startsWith(QUERIED_TOTAL),
    `the disputed bill is UNCHANGED at ${QUERIED_TOTAL} — a query is a marker, never an edit (hard rule 4)`,
  );
  // …and a second, undisputed bill is still there and untouched.
  const other = await api(page, `bills/${encodeURIComponent(OTHER_BILL)}`);
  check(
    other.status === 200,
    `the OTHER bill ${OTHER_BILL} is still served and unaffected (${other.status})`,
  );
  await noInternals(page, "CWP-055");

  // ═════ 7b · back to the hub, now that a query is in the list ═════════════
  //
  // ⚠ **THIS BLOCK IS HERE AND NOT IN STEP 1, AND THE MOVE IS THE POINT.** The
  // *WHAT* column is documented as the customer's own words. A query does not
  // type anything into it: the write composes a sentence for the CLERK's
  // worklist and stores it in the same column, and this table renders it
  // verbatim. **So the fault only exists once a customer has queried
  // something** — and checked in step 1 it read as FIXED on a freshly seeded
  // database and BROKEN on a second run, which is a check whose colour is
  // decided by how many times it has been run rather than by the product.
  // Checked HERE, after this run has sent a real query, the row is always
  // there and the answer is always about the product.
  console.log("\n── 7b · the query, as it now appears on the customer's own list ──");
  await page.goto(`${PORTAL}/requests`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-046"]', { timeout: 20000 });
  const hubTable = await page
    .locator('[data-screen="CWP-046"] table')
    .innerText()
    .catch(() => "");
  const queryRow = /Queried through the customer portal/i.test(hubTable);
  check(queryRow, "the query this run sent is on the customer's own requests list");
  // Hard rule 2 — money is STORED to four decimals and DISPLAYS at two. One
  // right answer, so this is asserted rather than recorded.
  const fourDp = hubTable.match(/\d+\.\d{4}\b/g) ?? [];
  record("CWP-046 four-decimal money in the table", fourDp.join(", ") || "(none)");
  check(
    fourDp.length === 0,
    `no money on CWP-046 is printed at four decimals (hard rule 2 — display 2): ${fourDp.join(", ")}`,
  );
  // ⚠ **THE WORDING HALF IS RECORDED, NOT ASSERTED**, because what this column
  // should SHOW a customer is a design decision and not a formatting one.
  gaps.known(
    queryRow && !/Their reason:/i.test(hubTable),
    "the WHAT column shows the customer's own words rather than the clerk's routing sentence",
    {
      defect: "DEF-CWP-4198",
      why:
        "a bill query composes a sentence for the CLERK's worklist and stores it in " +
        "what_they_said, which this column renders verbatim — so a customer reads " +
        "'Queried through the customer portal bill … Their reason: …' as their own words. " +
        "The four-decimal money inside it IS fixed; the marker, the ISO period and the " +
        "third person are the open half",
    },
  );
  await machineDates(page, "CWP-046 with a query on it");

  // ═════ 8 · ask a question — the bill travels with it ═════════════════════
  console.log("\n── 8 · CWP-054, a question that already names the bill ──");
  // ⚠ **BREATHE BEFORE THE LAST SCREEN.** This run opens five screens and sends
  // three writes inside a minute, and the portal throttles its guest reads per
  // window — two 429s on one run emptied both of this screen's controls. The
  // pause is not cosmetic: without it the walkthrough measures the rate limiter
  // rather than the product. The checks below ALSO cope with a 429 rather than
  // relying on this, because a sleep is a hope and not a guarantee.
  await page.waitForTimeout(3000);
  await page.goto(`${PORTAL}/ask-a-question?bill=${encodeURIComponent(QUERIED_BILL)}`, {
    waitUntil: "networkidle",
  });
  await page.waitForSelector('[data-screen="CWP-054"]', { timeout: 20000 });
  await page.screenshot({ path: join(OUT, "8-cwp-054-ask.png"), fullPage: true });

  const topics = await page.locator("#question-topic option").all();
  over(topics, "CWP-054 topic options", { min: 2 });

  // ⚠ **ASK THE SERVER WHAT IT WOULD SERVE, BEFORE JUDGING WHAT THE SCREEN
  // DREW — BECAUSE THIS SCREEN FAILS SILENTLY AND SO DID THIS CHECK.** On one
  // run the portal's rate limiter answered 429 to `getBills` and
  // `getPortalHelp`; the *Which bill* control then offered only *Not about one
  // bill* and the suggestions panel simply vanished, with nothing on the screen
  // saying anything had gone wrong. The first draft of this block reported that
  // as *"the panel is correctly ABSENT because this tenant publishes none"* —
  // a check that PASSED WRONGLY, asserting a cause it had never established
  // (hard-won law 7: *"ask what would make this check pass wrongly"*).
  // So the two facts are separated: what the server HAS, and what the screen
  // DREW. A mismatch is a failure; a server that refuses is a SKIP naming the
  // status, which is not a pass.
  const billsSaid = await api(page, "bills");
  const helpSaid = await page.evaluate(
    async (url) => {
      const answer = await fetch(url, { credentials: "include" });
      return { status: answer.status, body: await answer.text() };
    },
    `${API}/public/help`,
  );
  const billsServed =
    billsSaid.status === 200 ? (JSON.parse(billsSaid.body).bills ?? []).length : null;
  const answersServed =
    helpSaid.status === 200 ? (JSON.parse(helpSaid.body).answers ?? []).length : null;
  record("CWP-054 the server serves", `${billsServed ?? `HTTP ${billsSaid.status}`} bill(s), ${answersServed ?? `HTTP ${helpSaid.status}`} published answer(s)`);

  const billOptions = await page.locator("#question-bill option").allInnerTexts();
  record("CWP-054 bill options", JSON.stringify(billOptions.join(" | ")));
  if (billsServed === null) {
    skip(`the Which bill control — the bills read answered HTTP ${billsSaid.status}, so the empty control is the SERVER's answer and not the screen's fault`);
  } else if (wasThrottled("/portal/bills")) {
    skip(
      `the Which bill control — the BROWSER's own bills read was throttled (429), so the ` +
        `${billOptions.length} option(s) it drew say nothing about the screen. The API served ` +
        `${billsServed} bill(s) a moment later`,
    );
  } else {
    // one option per bill, plus the *not about one bill* entry.
    over(billOptions, "CWP-054 bill options", { expected: billsServed + 1 });
    check(
      billOptions.some((one) => one.includes(QUERIED_BILL)),
      `the bill control offers ${QUERIED_BILL} by its own number (B14 rule 31)`,
    );
  }

  // ⚠ **NO FILE INPUT ANYWHERE IN THE DOCUMENT** (`US-CWP-064` TC-3/4). The
  // drawing has an *Attach a photo* control; the deferral is signed, and this
  // is the claim that it was honoured — a claim only a browser can make.
  const fileInputs = await page.locator('input[type="file"]').count();
  check(fileInputs === 0, `there is NO file input in the DOM (${fileInputs}) — the upload deferral`);
  gaps.known(
    fileInputs > 0,
    "an ATTACH A PHOTO control on CWP-054 (wireframe P40 draws one)",
    {
      defect: "DEF-CWP-3988",
      why:
        "a signed deferral: customer uploads are staff-mediated in this product, so the control " +
        "renders as a held explanation rather than a picker. The same constraint blocks CWP-049",
    },
  );

  const suggestions = await page.locator("[data-answer]").all();
  const suggestionsPanel = await page.locator('[data-testid="question-suggestions"]').count();
  record("CWP-054 published answers drawn", `${suggestions.length}`);
  if (answersServed === null) {
    skip(`the MIGHT ANSWER IT NOW panel — the help read answered HTTP ${helpSaid.status}, so its absence is the SERVER's answer and proves nothing about the screen`);
  } else if (wasThrottled("/portal/public/help")) {
    skip(
      `the MIGHT ANSWER IT NOW panel — the BROWSER's own help read was throttled (429). The API ` +
        `served ${answersServed} published answer(s) a moment later`,
    );
  } else if (answersServed === 0) {
    // `BR-CWP-093` — ABSENT when nothing is published, never an empty panel.
    check(
      suggestionsPanel === 0 && suggestions.length === 0,
      "the suggestions panel is ABSENT rather than empty — the server publishes none (BR-CWP-093)",
    );
  } else {
    check(
      suggestionsPanel > 0,
      `the panel is DRAWN, because the server publishes ${answersServed} answer(s)`,
    );
    over(suggestions, "CWP-054 might-answer-it-now links", { min: 1 });
    check(
      suggestions.length === Math.min(3, answersServed),
      `…and it offers ${Math.min(3, answersServed)} of the ${answersServed} published (drew ${suggestions.length})`,
    );
  }

  // `US-CWP-066` TC-8 — two numbers, and the screen says which is which.
  const office = await page.locator('[data-phone="office"]').innerText().catch(() => "");
  const emergency = await page.locator('[data-phone="emergency"]').innerText().catch(() => "");
  record("CWP-054 office phone", JSON.stringify(office.trim()));
  record("CWP-054 emergency phone", JSON.stringify(emergency.trim()));
  const officeDigits = office.replace(/\D/g, "");
  const emergencyDigits = emergency.replace(/\D/g, "");
  check(
    officeDigits !== "" && emergencyDigits !== "" && officeDigits !== emergencyDigits,
    `the office and emergency numbers are DIFFERENT numbers (${officeDigits} vs ${emergencyDigits})`,
  );
  await noInternals(page, "CWP-054");
  allDates = allDates.concat(await machineDates(page, "CWP-054"));

  // ═════ 9 · what a customer reads a date as ═══════════════════════════════
  console.log("\n── 9 · the tenant's own date format, across all five screens ──");
  const frontBody = await page.evaluate(async (url) => (await fetch(url)).text(), `${API}/public/front`);
  const regional = JSON.parse(frontBody).regional ?? {};
  record("the tenant's date format", `${regional.date_format} (${regional.timeZone ?? regional.timezone})`);
  record("raw ISO dates counted across wave I's screens", `${allDates.length}`);
  check(
    allDates.length === 0,
    `no screen prints a raw machine date to a customer — the tenant asked for ` +
      `${regional.date_format} (${allDates.length} found: ${allDates.slice(0, 6).join(", ")})`,
  );

  await timings.report({
    targets: [
      { id: "RT-2", match: "/portal/auth/sign-in", p95: 900 },
      { id: "RT-3", match: "/portal/requests", p95: 600 },
    ],
  });

  console.log("\n── every figure this run read off the screen ──");
  for (const line of figures) console.log(`   ${line}`);

  if (refused.size) {
    console.log("\n── reads the portal THROTTLED during this run (429) ──");
    for (const [path, n] of refused) console.log(`   ${n}× ${path}`);
    console.log("   A control that is empty because its read was refused is skipped above, not failed.");
  }

  if (skipped.length) {
    console.log("\n── not exercised (NOT passes) ──");
    for (const one of skipped) console.log(`   ⏭ ${one}`);
  }

  await browser.close();
  // ⚠ **THE COUNTS PRINT EVEN ON A PASS.** `0 failures, 4 known gaps` must
  // never look like `0 failures, 0 known gaps` — law 7's fifth shape, a
  // declared blind spot with no NUMBER attached being indistinguishable from
  // an empty one.
  console.log(`\n── ${skipped.length} step(s) skipped, ${figures.length} figure(s) read ──`);
  process.exit(gaps.report(failures));
})().catch((error) => {
  console.error(error);
  process.exit(2);
});
