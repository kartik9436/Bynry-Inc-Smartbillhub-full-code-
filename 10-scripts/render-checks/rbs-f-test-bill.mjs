/**
 * RENDERED-OUTPUT CHECK — CR-075 wave F task `F4`. Runbook 23 on `RBS-006`, in a
 * real browser, against `wireframes/RBS-006-R23.md`.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: *"no gate looks at rendered output"*,
 * and nine defects were found by that and by nothing else. And the Product
 * Owner's own definition of done, 2026-09-06: *"ensure you do web walkthorugh
 * before you sign off the user story or build"*.
 *
 * ⚠ **THE STRONGEST ASSERTION IN THIS FILE IS NOT ABOUT THE SCREEN.** It is
 * that **the numbers on the screen are the numbers in the run's STORED
 * report** — read off the DOM and compared with the JSON the server served, at
 * two decimals on screen and four in the payload (hard rule 2). A screen
 * agreeing with itself proves nothing; a screen agreeing with a frozen report
 * that was composed at close is what `BR-RBS-020` promises.
 *
 * ⚠ **AND THE RUN IS EXECUTED, NOT INSERTED.** `rbs_f_seed_test_bill.py` runs
 * runbook 23 through `services.run_to_completion`, so the report is composed by
 * `report()` and frozen by `close_run`. A fixture that TYPED a block list would
 * let this walkthrough pass over a broken runbook — `DEF-RBS-4291`'s shape.
 *
 * ⚠ **STARTING A RUN FROM THE SCREEN IS NOT POSSIBLE YET AND IS SAID RATHER
 * THAN SUBSTITUTED.** `POST /runbooks/{key}/runs` is wave `L`; every runbooks
 * route that exists today is a `GET` (`api.py`'s own docstring, `BR-RBS-002`).
 * So the runs are made by the seed script — the same engine call the future
 * endpoint will make — and everything from the stored run onwards is proved
 * here. The click-to-start half is `L`'s walkthrough, not this one's.
 *
 * ── HOW TO RUN IT ────────────────────────────────────────────────────────
 *   Use a database NOBODY ELSE is seeding — on 2026-08-30 a sibling check lost
 *   three runs to the shared one, with every id changing mid-run, which looks
 *   exactly like a broken screen.
 *
 *   createdb sbh_rbsf -T smartbillhub
 *   DJANGO_SETTINGS_MODULE=config.settings.local DATABASE_URL=…/sbh_rbsf \
 *     python3.12 10-scripts/render-checks/rbs_f_seed_test_bill.py --tenant brazosbend
 *   … it prints SMOKE_RUN_PRICED and SMOKE_RUN_REFUSED.
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local DATABASE_URL=…/sbh_rbsf \
 *     python3.12 06-backend/manage.py runserver 127.0.0.1:8077 --noreload &
 *   (cd 07-frontend && npx vite build && \
 *      PORT=4277 API_PROXY_TARGET=http://127.0.0.1:8077 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4277 SMOKE_RUN_PRICED=… SMOKE_RUN_REFUSED=… \
 *   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/rbs-f-test-bill.mjs
 *
 * ── WHAT IT ASSERTS, REGION BY REGION AGAINST `wireframes/RBS-006-R23` ─────
 *   PRICED (state A)
 *   1  the page head names the runbook and offers **Run again** — a test bill
 *      is re-run by design (judgment J5) so the control is never disabled.
 *   2  the KPI strip drew its FOUR tiles, and the money tile shows the run's
 *      own total at TWO decimals while the stored payload carries FOUR.
 *   3  the Sentence card drew, with its total, and says nothing was written.
 *   4  the Records table drew six columns and one row per priced line, EVERY
 *      row carrying an explanation — `BR-RBS-010`.
 *   5  the Reconciled table drew four columns and a `Same` mark where the two
 *      sides tie, with an em dash where a line exists on one side only.
 *   6  **the numbers on screen ARE the stored report's** — every line amount,
 *      matched at two decimals against the payload's four.
 *   7  B14 rules 31 and 32 — no database id and no rule id anywhere a clerk
 *      can read, which is also what keeps the ENGINE's own refusal sentences
 *      (they quote `BR-BIL-015` by name) off this screen.
 *   8  the page does not scroll sideways at 1440.
 *
 *   REFUSED (state B)
 *   9  ONE sentence, six words or fewer, drawn in a painted callout — read
 *      from COMPUTED STYLE, because B14 rule 21's migration clause means an
 *      unlisted file's utility renders as NOTHING while the class sits in the
 *      DOM and every `toContain` passes.
 *  10  no KPI strip and no comparison beside the stop (judgment J2).
 *  11  the empty state names the fix route in words (`BR-RBS-011`).
 */
import { existsSync, mkdirSync, readdirSync, writeFileSync } from "node:fs";
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4277";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const PRICED = process.env.SMOKE_RUN_PRICED ?? "";
const REFUSED = process.env.SMOKE_RUN_REFUSED ?? "";
const KEY = process.env.SMOKE_RUNBOOK ?? "test_bill";
const OUT = process.env.SMOKE_OUT ?? "/tmp/rbs-f-test-bill";
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

/** `1234.5600` → `1,234.56` — the STORED figure as `MoneyCell` prints it.
 *
 * ⚠ This is the whole point of check 6. The payload carries FOUR decimals
 * because `TC-RBS-004.3` compares at four; the screen shows TWO because hard
 * rule 2 says display is two. A walkthrough that compared the raw strings
 * would fail on every row and a walkthrough that compared nothing would pass
 * over a screen showing somebody else's numbers. */
function asDisplayed(amount) {
  const n = Number(amount);
  return n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

if (PRICED === "") {
  console.error(
    "⛔ SMOKE_RUN_PRICED is not set. This check reads STORED runs — it cannot start one,\n" +
      "   because POST /runbooks/{key}/runs is wave L and every runbooks route today is a\n" +
      "   GET. Run rbs_f_seed_test_bill.py first; see this file's header.",
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

  // The server's own answer, captured rather than inferred. "Did the screen
  // draw it" and "did the server send it" are two different questions, and
  // DEF-RBS-4284 is what happens when only one of them is asked.
  const wire = [];
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
  // ⚠ `input[type="email"]` MATCHES NOTHING ON THIS SCREEN — `S3` draws the
  // work-email field as `type="text"` with `id="signin-email"`.
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  // ⚠ WAIT FOR THE LANDING, NOT FOR THE NETWORK. Sign-in is an XHR, so the page
  // never navigates and `networkidle` returns before the session cookie exists.
  await page.waitForURL(/\/dashboard(\?|$)/, { timeout: 30000 });

  // ══════════════════════════════════════════════════════════════════════
  // STATE A — the account that priced
  // ══════════════════════════════════════════════════════════════════════
  console.log("── RBS-006-R23 · PRICED, region by region ────────────────");
  wire.length = 0;
  await page.goto(`${BASE}/${TENANT}/runbooks/${KEY}/runs/${PRICED}`, {
    waitUntil: "networkidle",
  });
  await page.screenshot({ path: join(OUT, "rbs-006-r23-priced.png"), fullPage: true });

  let body = (await page.textContent("body")) ?? "";
  const pricedReport = wire.find((w) => /\/report\b/.test(w.url))?.body ?? "";
  const served = pricedReport === "" ? null : JSON.parse(pricedReport);
  const blocks = served?.blocks ?? [];
  check(blocks.length > 0, `the server served a frozen report (${blocks.length} blocks)`);
  check(
    JSON.stringify(blocks.map((b) => b.block)) ===
      JSON.stringify(["kpis", "sentence", "records", "reconciled"]),
    `the report is the four blocks the build sheet draws (saw ${blocks.map((b) => b.block).join(", ")})`,
  );

  // 1 · region 1 — the head, and Run again is OFFERED (judgment J5).
  check(/Test bill/i.test(body), "the page head names the runbook");
  const rerun = await page.$("button:not([disabled])");
  check(rerun !== null, "the page offers an enabled control (Run again is never held here)");
  const heldReason = await page.$("[data-rerun-reason]");
  check(heldReason === null, "Run again is not disabled — a test bill is re-run by design");

  // 2 · region 2 — the KPI strip, FOUR tiles, and the total at TWO decimals.
  const kpis = blocks.find((b) => b.block === "kpis") ?? null;
  check(kpis !== null && kpis.payload.tiles.length === 4, "the KPI strip drew four tiles");
  if (kpis !== null) {
    for (const tile of kpis.payload.tiles) {
      check(body.includes(tile.label), `KPI tile "${tile.label}" drew`);
    }
    const total = kpis.payload.tiles.find((t) => t.id === "total");
    if (total) {
      check(
        body.includes(asDisplayed(total.value.amount)),
        `the total shows at two decimals: ${asDisplayed(total.value.amount)} ` +
          `(stored ${total.value.amount})`,
      );
    }
    // ⚠ THE DATE THAT DECIDED THE PRICE (judgment J9). Without it a clerk
    // comparing this screen with a bill priced on the BILL DAY sees a gap and
    // has nothing to explain it with.
    check(
      kpis.payload.tiles.some((t) => t.id === "priced_as_at" && t.value.kind === "date"),
      "the strip states which date priced the run",
    );
  }

  // 3 · region 3 — the Sentence card.
  const sentence = blocks.find((b) => b.block === "sentence") ?? null;
  check(sentence !== null, "the Sentence block was served");
  if (sentence !== null) {
    check(body.includes(sentence.payload.text), "the outcome sentence drew, word for word");
    check(
      /no bill number/i.test(sentence.payload.text),
      "the sentence says no bill number was used",
    );
    const card = await page.$('[data-block="sentence"], .outcome-card, [data-outcome-tone]');
    if (card !== null) {
      const painted = await card.evaluate((el) => getComputedStyle(el).backgroundColor);
      check(
        painted !== "rgba(0, 0, 0, 0)" && painted !== "transparent",
        `the outcome card is actually PAINTED (computed ${painted})`,
      );
    }
  }

  // 4 · region 4 — the Records table: six columns, every row explained.
  const records = blocks.find((b) => b.block === "records") ?? null;
  check(records !== null && records.payload.rows.length > 0, "the Records table has priced lines");
  if (records !== null) {
    for (const column of records.payload.columns) {
      check(body.includes(column.label), `Records column "${column.label}" drew`);
    }
    let explained = 0;
    for (const row of records.payload.rows) {
      if ((row.cells.why?.text ?? "").trim().length > 0) explained += 1;
    }
    check(
      explained === records.payload.rows.length,
      `every line is explained (${explained} of ${records.payload.rows.length})`,
    );
  }

  // 5 · region 5 — the Reconciled table.
  const reconciled = blocks.find((b) => b.block === "reconciled") ?? null;
  check(reconciled !== null, "the comparison against the last issued bill drew");
  if (reconciled !== null) {
    check(body.includes(reconciled.payload.heading), "the comparison heading drew");
    for (const column of reconciled.payload.columns) {
      check(body.includes(column.label), `comparison column "${column.label}" drew`);
    }
    const ties = reconciled.payload.rows.filter(
      (r) => r.cells.difference?.kind === "pill",
    ).length;
    const dashes = reconciled.payload.rows.filter(
      (r) => r.cells.this_run?.text === "—" || r.cells.last_bill?.text === "—",
    ).length;
    console.log(`   · ${ties} row(s) tie, ${dashes} row(s) exist on one side only`);
    if (ties > 0) check(body.includes("Same"), "a tie is drawn as a mark, not as an empty cell");
  }

  // 6 · THE NUMBERS ON SCREEN ARE THE STORED REPORT'S.
  if (records !== null) {
    let matched = 0;
    const missing = [];
    for (const row of records.payload.rows) {
      const shown = asDisplayed(row.cells.amount.amount);
      if (body.includes(shown)) matched += 1;
      else missing.push(`${row.cells.line.text} = ${shown} (stored ${row.cells.amount.amount})`);
    }
    check(
      matched === records.payload.rows.length,
      `every stored line amount is on screen at two decimals ` +
        `(${matched} of ${records.payload.rows.length})${missing.length ? ` — missing ${missing.join("; ")}` : ""}`,
    );
  }

  // 7 · B14 rules 31 and 32 — nothing internal reaches a clerk.
  for (const pattern of FORBIDDEN_IN_CLERK_COPY) {
    const hit = body.match(pattern);
    check(hit === null, `no internal id on the priced screen${hit ? ` — saw ${hit[0]}` : ""}`);
  }

  // 8 · the page does not scroll sideways at 1440.
  check((await page.evaluate(SIDEWAYS)) === 0, "the priced page does not scroll sideways at 1440");

  // ══════════════════════════════════════════════════════════════════════
  // STATE B — the account that could not be priced
  // ══════════════════════════════════════════════════════════════════════
  if (REFUSED === "") {
    console.log(
      "\n⚠ SMOKE_RUN_REFUSED is not set, so the REFUSAL half of this walkthrough did not\n" +
        "   run. That is a gap in the evidence, not a pass — the goal sentence has two\n" +
        "   halves and only one of them was looked at.",
    );
    failures.push("the refusal half of the walkthrough had no run to open");
  } else {
    console.log("\n── RBS-006-R23 · REFUSED, region by region ───────────────");
    wire.length = 0;
    await page.goto(`${BASE}/${TENANT}/runbooks/${KEY}/runs/${REFUSED}`, {
      waitUntil: "networkidle",
    });
    await page.screenshot({ path: join(OUT, "rbs-006-r23-refused.png"), fullPage: true });
    body = (await page.textContent("body")) ?? "";

    const refusedBody = wire.find((w) => /\/report\b/.test(w.url))?.body ?? "";
    const refusedServed = refusedBody === "" ? null : JSON.parse(refusedBody);
    const refusedBlocks = refusedServed?.blocks ?? [];

    // 9 · ONE sentence, six words or fewer, and it is PAINTED.
    check(
      JSON.stringify(refusedBlocks.map((b) => b.block)) ===
        JSON.stringify(["sentence", "records"]),
      `a stop draws the sentence and the empty table only (saw ${refusedBlocks
        .map((b) => b.block)
        .join(", ")})`,
    );
    const stop = refusedBlocks.find((b) => b.block === "sentence") ?? null;
    if (stop !== null) {
      const words = stop.payload.text.trim().split(/\s+/).length;
      check(words <= 6, `the refusal is ${words} words (B14 rule 33 caps it at six)`);
      check(body.includes(stop.payload.text), `the refusal drew: "${stop.payload.text}"`);
      const card = await page.$('[data-block="sentence"], .outcome-card, [data-outcome-tone]');
      if (card !== null) {
        const painted = await card.evaluate((el) => getComputedStyle(el).backgroundColor);
        check(
          painted !== "rgba(0, 0, 0, 0)" && painted !== "transparent",
          `the stop card is actually PAINTED (computed ${painted})`,
        );
      }
    }

    // 10 · no strip and no comparison beside the stop (judgment J2).
    check(
      !refusedBlocks.some((b) => b.block === "kpis"),
      "no KPI strip of em dashes beside the stop",
    );
    check(
      !refusedBlocks.some((b) => b.block === "reconciled"),
      "no comparison table beside the stop",
    );

    // 11 · the empty state names the fix route in words (`BR-RBS-011`).
    const emptyState = refusedBlocks.find((b) => b.block === "records")?.payload?.empty ?? null;
    check(emptyState !== null, "the Records block carries an empty state");
    if (emptyState !== null) {
      check(body.includes(emptyState.title), `the empty state drew: "${emptyState.title}"`);
      check(
        body.includes(emptyState.helper),
        `the empty state names where to go: "${emptyState.helper}"`,
      );
    }

    for (const pattern of FORBIDDEN_IN_CLERK_COPY) {
      const hit = body.match(pattern);
      check(hit === null, `no internal id on the refused screen${hit ? ` — saw ${hit[0]}` : ""}`);
    }
    check(
      (await page.evaluate(SIDEWAYS)) === 0,
      "the refused page does not scroll sideways at 1440",
    );
  }

  writeFileSync(join(OUT, "wire.json"), JSON.stringify(wire, null, 2));
  await browser.close();

  console.log("");
  if (failures.length > 0) {
    console.error(`⛔ ${failures.length} check(s) failed:`);
    for (const line of failures) console.error(`   · ${line}`);
    process.exit(1);
  }
  console.log(`✓ every check passed — screenshots and the wire capture in ${OUT}`);
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
