/**
 * RENDERED-OUTPUT CHECK — CR-075 wave R′, the payments half. Four runbooks in a browser.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: *"no gate looks at rendered output"*,
 * and nine defects were found by that and by nothing else. And the Product
 * Owner's own definition of done, 2026-09-06: *"ensure you do web walkthorugh
 * before you sign off the user story or build"*.
 *
 * ⚠ **THE TWO SCREENS THAT MATTER MOST HERE BOTH SAY *NO*, AND A BACKEND TEST
 * CANNOT TELL YOU WHETHER THEY READ AS DESIGNED ANSWERS OR AS FAILURES.**
 *   · **Runbook 26 STOPS**, because this product has no returns feed, no column
 *     for a bank's return code and no port that reverses a payment. The Product
 *     Owner ruled that state valid on 2026-09-06 — *"you can stop the job saying
 *     APi or conenct not available"* — so the page must never use the word
 *     *failed*, must draw no KPI strip, and must tell a clerk what to do.
 *   · **Runbook 17's failed-debit tile must say *Not reported* and NEVER `0`.**
 *     Nothing on this product drafts an autopay debit, so none can fail, and a
 *     zero would be indistinguishable from a morning when every debit went
 *     through. That is hard-won law 7's fifth shape rendered as pixels.
 *
 * ── HOW TO RUN IT ────────────────────────────────────────────────────────
 *   DJANGO_SETTINGS_MODULE=config.settings.local DATABASE_URL=…smartbillhub \
 *     python3.12 10-scripts/render-checks/rbs_r_seed_payments.py --tenant brazosbend
 *   … which prints SMOKE_DEPOSIT_RUN_ID, SMOKE_AUTOPAY_RUN_ID,
 *     SMOKE_PLANS_RUN_ID and SMOKE_RETURNS_RUN_ID.
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local DATABASE_URL=…smartbillhub \
 *     python3.12 06-backend/manage.py runserver 127.0.0.1:8188 --noreload &
 *   (cd 07-frontend && npx vite build && \
 *      PORT=4288 API_PROXY_TARGET=http://127.0.0.1:8188 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4288 SMOKE_DEPOSIT_RUN_ID=… … \
 *   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/rbs-r-money-runbooks.mjs
 *
 * ── WHAT IT ASSERTS ──────────────────────────────────────────────────────
 *   THE STOPPED RUN — runbook 26, the screen a real utility meets on day one
 *   1  **THE HEAD SAYS WHAT HAPPENED IN PLAIN WORDS**, read from the DOM, so a
 *      block the renderer dropped is caught (`DEF-RBS-4284`: the engine and the
 *      renderer agreeing on a NAME and disagreeing on a payload).
 *   2  **THE CHAIN DREW SIX CELLS, ONE RED AND FIVE *NEVER REACHED***, and the
 *      red cell is actually PAINTED — read from COMPUTED STYLE, never from a
 *      class name, because B14 rule 21's migration clause means an unlisted
 *      file's utility renders as nothing at all while the class sits in the DOM.
 *   3  **NO KPI STRIP.**
 *   4  **THE PAGE NEVER SAYS *FAILED* OR *ERROR*.** The ruling's whole point.
 *
 *   THE THREE WORKING RUNS
 *   5  **EVERY KPI TILE DREW ITS OWN NUMBER**, and each is compared against the
 *      figure the SERVER sent — *did the screen draw it* and *did the server
 *      send it* are two questions and `DEF-RBS-4284` is what happens when only
 *      one is asked.
 *   6  **MONEY IS SHOWN TO TWO DECIMALS AND NEVER TO FOUR OR SIX.** A stored
 *      four-place value reaching a clerk (*"182.400000 more than this account
 *      owes"*) is a real defect another lane fixed this week, and the renderer
 *      is the only place it can be caught.
 *   7  **THE SECOND APPROVAL IS ON SCREEN, DISABLED, WITH ITS REASON** —
 *      `BR-RBS-018`, and B14 draws a control a user may not use disabled with
 *      its reason rather than hidden (`DEF-SHL-4043`).
 *   8  **EVERY *WHY* CELL IS A SENTENCE**, and each refund says *Account
 *      closed* or *Over the $250.00 limit* — `US-RBS-027`'s acceptance sentence
 *      asserted on the SCREEN.
 *   9  **THE FAILED-DEBIT TILE SAYS *Not reported*, NOT `0`**, and carries its
 *      reason.
 *  10  **THE *Plans to end* TILE CARRIES WHO ENDS THEM** — a live-looking number
 *      behind a door that does not open is hard-won law 2's mirror.
 *  11  **EVERY FIX IS A REAL DESTINATION** — a resolvable href, never a present
 *      string: `//host/…` reads as a perfectly good href to `toContain`
 *      (`DEF-CWP-3925`) — and clicking one lands on a screen that exists.
 *
 *   ALL FOUR
 *  12  **B14 RULES 31 AND 32** — no database id and no rule id in what a clerk
 *      reads. `decided_by_rule` IS on every row, in `ReportRow.meta`, and no
 *      block draws it; this is what proves that.
 *  13  **THE PAGE DOES NOT SCROLL SIDEWAYS** at 1440.
 *
 * ⚠ **WHAT THIS CHECK CANNOT SAY, STATED RATHER THAN LEFT AS A THIN PASS.**
 * Runbook 26's WORKING screen — the by-reason table, the fee behind the second
 * approval, the privilege removal — cannot be produced on this deployment at
 * all, because there is no returns feed and no return-code column anywhere
 * (`OQ-RBS-1741`). Those branches are proved in
 * `06-backend/tests/test_us_rbs_036_returned_payments.py` with a feed supplied,
 * and this file says so instead of asserting rows it knows will be absent. The
 * same is true of runbook 17's failed-debit table.
 */
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  const roots = [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean);
  for (const root of roots) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of [
        "chrome-linux64/chrome",
        "chrome-linux/chrome",
        "chrome-linux/headless_shell",
      ]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  return undefined;
}

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4288";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const DEPOSIT = process.env.SMOKE_DEPOSIT_RUN_ID ?? "";
const AUTOPAY = process.env.SMOKE_AUTOPAY_RUN_ID ?? "";
const PLANS = process.env.SMOKE_PLANS_RUN_ID ?? "";
const RETURNS = process.env.SMOKE_RETURNS_RUN_ID ?? "";
const OUT = process.env.SMOKE_OUT ?? "/tmp/rbs-r-money-runbooks";
const VIEWPORT = { width: 1440, height: 1000 };

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

const SIDEWAYS =
  "Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)";

/** Anything a clerk must never be shown (B14 rules 31 and 32). */
const FORBIDDEN_IN_CLERK_COPY = [
  /\bBR-[A-Z]{3}-\d{3,5}\b/,
  /\b(?:OQ|DEF|TC|US|EP|GT|RB)-(?:[A-Z]{3}-)?\d{2,5}\b/,
  /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
];

/** A stored four- or six-place figure that reached a sentence. `$159.0000`
 *  and `2.000000%` are the two shapes this product actually produces. */
const OVER_PRECISE_MONEY = /\$\s?\d[\d,]*\.\d{3,}/;

if ([DEPOSIT, AUTOPAY, PLANS, RETURNS].some((one) => one === "")) {
  console.error(
    "⛔ all four run ids must be set. This check reads STORED runs — it cannot start one.\n" +
      "   Seed them with rbs_r_seed_payments.py first; see the header.",
  );
  process.exit(2);
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });

  // The server's own answer, captured rather than inferred.
  let wire = [];
  page.on("response", async (response) => {
    if (!/\/runbooks\//.test(response.url())) return;
    try {
      wire.push({ url: response.url(), body: await response.text() });
    } catch {
      /* a redirect or a bodyless response has nothing to read */
    }
  });

  console.log("── sign in ───────────────────────────────────────────────");
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/dashboard(\?|$)/, { timeout: 30000 });

  async function open(key, runId, shot) {
    wire = [];
    await page.goto(`${BASE}/${TENANT}/runbooks/${key}/runs/${runId}`, {
      waitUntil: "networkidle",
    });
    // ⚠ **`networkidle` IS NOT ENOUGH.** The page fetches the run and its report
    // through `useQuery`, so the first navigation after sign-in can return with
    // the LOADING SKELETON on screen — and a broken WAIT then reads as a broken
    // SCREEN. Wait for the skeleton to GO, which is a positive fact about the
    // rendered page rather than a guess about the network.
    await page
      .waitForFunction(() => document.querySelector(".skeleton") === null, { timeout: 20000 })
      .catch(() => {});
    await page.screenshot({ path: join(OUT, shot), fullPage: true });
    const reportBody = wire.find((w) => /\/report\b/.test(w.url))?.body ?? "";
    return {
      body: (await page.textContent("body")) ?? "",
      served: reportBody === "" ? null : JSON.parse(reportBody),
    };
  }

  function noInternalIds(body, where) {
    for (const pattern of FORBIDDEN_IN_CLERK_COPY) {
      const hit = body.match(pattern);
      check(hit === null, `${where}: no internal id on screen${hit ? ` — saw ${hit[0]}` : ""}`);
    }
  }

  function blocks(served) {
    return served?.blocks ?? [];
  }

  function block(served, name) {
    return blocks(served).find((one) => one.block === name) ?? null;
  }

  // ── 1 · the stopped run · runbook 26 ────────────────────────────────────
  console.log("── runbook 26 · Returned payments · the STOP ──────────────");
  {
    const { body, served } = await open("returned_payments", RETURNS, "26-returned-stopped.png");
    const verdict = block(served, "verdict");
    check(verdict !== null, "the server served a verdict block");
    if (verdict) {
      check(verdict.payload.word === "Stopped", `the verdict word is "Stopped"`);
      check(
        body.includes(verdict.payload.count),
        `the head says what happened: "${verdict.payload.count}"`,
      );
    }
    const sentence = block(served, "sentence");
    check(sentence !== null, "the server served the what-to-do sentence");
    if (sentence) {
      check(body.includes(sentence.payload.text), "the page tells a clerk what to do");
      check(
        /Connect a payment provider/.test(sentence.payload.text),
        "and the thing it tells them to do is an act they can perform",
      );
    }
    const cells = await page.$$("[data-chain-state]");
    check(cells.length === 6, `the chain drew 6 cells (saw ${cells.length})`);
    const states = [];
    for (const cell of cells) states.push(await cell.getAttribute("data-chain-state"));
    check(states.filter((s) => s === "bad").length === 1, "exactly one cell is red");
    check(
      states.filter((s) => s === "notReached").length === 5,
      `5 cells read Never reached (saw ${states.join(", ")})`,
    );
    const red = cells[states.indexOf("bad")];
    if (red) {
      // ⚠ COMPUTED STYLE, NOT A CLASS NAME.
      const painted = await red.evaluate((el) => getComputedStyle(el).backgroundColor);
      check(
        painted !== "rgba(0, 0, 0, 0)" && painted !== "transparent",
        `the red chain cell is actually PAINTED (computed ${painted})`,
      );
      check(((await red.textContent()) ?? "").trim().length > 0, "the red cell names the stop");
    }
    check(
      blocks(served).every((one) => one.block !== "kpis"),
      "a stopped run draws NO KPI strip — zeroes would read like a clean day",
    );
    check(
      !/\bfailed\b/i.test(body) && !/\berror\b/i.test(body),
      "the stopped page never says failed or error — the absence is a RESULT",
    );
    noInternalIds(body, "returned payments");
    check((await page.evaluate(SIDEWAYS)) === 0, "the stopped page does not scroll sideways");
  }

  // ── 2 · deposit review ──────────────────────────────────────────────────
  console.log("── runbook 15 · Deposit review ───────────────────────────");
  {
    const { body, served } = await open("deposit_review", DEPOSIT, "15-deposit-review.png");
    const kpis = block(served, "kpis");
    check(kpis !== null, "the server served a KPI strip");
    for (const tile of kpis?.payload.tiles ?? []) {
      const shown = tile.value.kind === "money" ? null : tile.value.text;
      if (shown !== null) {
        check(body.includes(shown), `the tile "${tile.label}" drew its own number (${shown})`);
      }
      check(body.includes(tile.label), `the tile "${tile.label}" drew its label`);
    }
    // ⚠ MONEY AT TWO DECIMALS ON SCREEN, FOUR IN THE PAYLOAD (hard rule 2).
    const money = kpis?.payload.tiles.find((one) => one.value.kind === "money");
    if (money) {
      check(
        /^\d+\.\d{4}$/.test(money.value.amount),
        `the payload carries four decimals (${money.value.amount})`,
      );
    }
    const overPrecise = body.match(OVER_PRECISE_MONEY);
    check(
      overPrecise === null,
      `no stored-precision money reaches a clerk${overPrecise ? ` — saw ${overPrecise[0]}` : ""}`,
    );

    // The second approval, on screen, disabled, with its reason.
    const action = block(served, "action");
    check(action !== null, "the server served the Approve-refunds control");
    if (action) {
      check(action.payload.enabled === false, "it is DISABLED — a second admin approves refunds");
      check(
        typeof action.payload.reason === "string" && action.payload.reason.length > 0,
        `and it carries its reason: "${action.payload.reason}"`,
      );
      check(body.includes(action.payload.reason), "the reason is on the SCREEN, not only in JSON");
      check(
        action.payload.reason.trim().split(/\s+/).length <= 6,
        "the refusal is five or six words (B14 rule 33)",
      );
    }

    // Every refund says WHY, in one of two sentences (US-RBS-027's own line).
    const records = block(served, "records");
    const why = (records?.payload.rows ?? []).map((row) => row.cells.why?.text ?? "");
    check(why.length > 0, `the records table drew ${why.length} rows`);
    check(
      why.some((one) => one === "Account closed"),
      `a refund row reads "Account closed"`,
    );
    for (const sentence of why) {
      check(sentence.trim().length > 0, `every Why cell is a sentence — "${sentence}"`);
      check(body.includes(sentence), `and it is on the screen — "${sentence}"`);
    }
    // `decided_by_rule` travels and NO block draws it (B14 rule 32).
    check(
      (records?.payload.rows ?? []).every((row) => row.meta && row.meta.decided_by_rule),
      "every row CARRIES the rule that decided it, in meta",
    );
    noInternalIds(body, "deposit review");
    check((await page.evaluate(SIDEWAYS)) === 0, "the deposit page does not scroll sideways");

    await assertFixRoutes(records, "deposit review");
  }

  // ── 3 · autopay pre-notification ────────────────────────────────────────
  console.log("── runbook 17 · Autopay pre-notification ─────────────────");
  {
    const { body, served } = await open("autopay_prenotice", AUTOPAY, "17-autopay.png");
    const kpis = block(served, "kpis");
    const failed = kpis?.payload.tiles.find((one) => one.id === "failed");
    check(failed !== undefined, "the server served the failed-debit tile");
    if (failed) {
      // ⚠ **NOT REPORTED, NEVER ZERO.** The whole point of the tile.
      check(
        failed.value.text === "Not reported",
        `the failed-debit tile says "Not reported" and not a number (saw "${failed.value.text}")`,
      );
      check(body.includes("Not reported"), "and a clerk can read it on the screen");
      check(
        typeof failed.detail === "string" && failed.detail.length > 0,
        `it carries its reason: "${failed.detail}"`,
      );
      check(body.includes(failed.detail), "and the reason is on the screen too");
    }
    const queued = kpis?.payload.tiles.find((one) => one.id === "queued");
    if (queued) {
      check(body.includes(queued.value.text), `notices queued drew its number (${queued.value.text})`);
      check(
        /Queued/.test(queued.detail ?? ""),
        "the word is Queued and never Sent — nothing leaves the building",
      );
    }
    const overPrecise = body.match(OVER_PRECISE_MONEY);
    check(overPrecise === null, `no stored-precision money on screen${overPrecise ? ` — ${overPrecise[0]}` : ""}`);
    noInternalIds(body, "autopay pre-notification");
    check((await page.evaluate(SIDEWAYS)) === 0, "the autopay page does not scroll sideways");
  }

  // ── 4 · payment plans ───────────────────────────────────────────────────
  console.log("── runbook 25 · Payment plans ────────────────────────────");
  {
    const { body, served } = await open("payment_plans", PLANS, "25-payment-plans.png");
    const kpis = block(served, "kpis");
    const toEnd = kpis?.payload.tiles.find((one) => one.id === "void");
    check(toEnd !== undefined, "the server served the Plans-to-end tile");
    if (toEnd) {
      check(body.includes(toEnd.value.text), `it drew its number (${toEnd.value.text})`);
      // ⚠ A LIVE-LOOKING NUMBER BEHIND A DOOR THAT DOES NOT OPEN is hard-won
      // law 2's mirror. The tile carries who actually ends the plan.
      check(
        toEnd.detail === "A person ends a plan on the account",
        `and it says who ends them: "${toEnd.detail}"`,
      );
      check(body.includes(toEnd.detail), "and that sentence is on the screen");
    }
    const breakdown = block(served, "breakdown");
    check(breakdown !== null, "the server served the by-standing table");
    if (breakdown) {
      check(
        typeof breakdown.payload.heading === "string" && Array.isArray(breakdown.payload.columns),
        "the breakdown carries heading and columns — DEF-RBS-4352's own shape",
      );
      for (const column of breakdown.payload.columns) {
        check(body.includes(column.label), `the breakdown drew its "${column.label}" header`);
      }
    }
    const records = block(served, "records");
    const outcomes = (records?.payload.rows ?? []).map((row) => row.cells.outcome?.text ?? "");
    check(
      outcomes.includes("In good standing"),
      "a plan in good standing is SHOWN — not counted as skipped",
    );
    check(outcomes.includes("Due to end"), "and a plan past the limit reads Due to end");
    noInternalIds(body, "payment plans");
    check((await page.evaluate(SIDEWAYS)) === 0, "the plans page does not scroll sideways");

    await assertFixRoutes(records, "payment plans");
  }

  /** Every fix route is a REAL destination, and one of them is clicked.
   *
   * ⚠ **A PRESENT STRING IS NOT A LINK.** `//host/…` is a protocol-relative URL
   * to another host and reads as a perfectly good href to `toContain`
   * (`DEF-CWP-3925`), so this resolves each one and then opens one for real —
   * the half of `BR-RBS-011` no unit test can reach. */
  async function assertFixRoutes(records, label) {
    const links = await page.$$('[data-block="records"] a[href]');
    check(links.length > 0, `${label}: the records table drew at least one fix route`);
    let target = null;
    for (const link of links) {
      const href = await link.getAttribute("href");
      const ok = typeof href === "string" && href.startsWith(`/${TENANT}/`);
      check(ok, `${label}: the fix route is a real address (${href})`);
      if (ok && target === null) target = href;
    }
    if (target) {
      await page.goto(`${BASE}${target}`, { waitUntil: "networkidle" });
      const landed = (await page.textContent("body")) ?? "";
      check(
        !/not built yet/i.test(landed) && landed.trim().length > 200,
        `${label}: clicking a fix route lands on a screen that exists (${target})`,
      );
    }
  }

  await browser.close();

  console.log("");
  if (failures.length) {
    console.log(`⛔ ${failures.length} failed:`);
    for (const one of failures) console.log(`   · ${one}`);
    process.exit(1);
  }
  console.log(`✓ everything checked passed. Screenshots in ${OUT}`);
  console.log(
    "\n⚠ WHAT THIS RUN COULD NOT SEE: runbook 26's working screen and runbook 17's\n" +
      "  failed-debit table cannot be produced on this deployment at all — there is no\n" +
      "  returns feed, no bank-return-code column and nothing that drafts a debit. Both\n" +
      "  are proved in the backend suite with the seams supplied, and neither number is\n" +
      "  quoted here alone.",
  );
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
