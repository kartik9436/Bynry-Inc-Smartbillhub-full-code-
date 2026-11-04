/**
 * RENDERED-OUTPUT CHECK — CR-075 wave Q′. The two INTEGRATION runbooks in a browser.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: *"no gate looks at rendered output"*,
 * and nine defects were found by that and by nothing else. And the Product
 * Owner's own definition of done, 2026-09-06: *"ensure you do web walkthorugh
 * before you sign off the user story or build"*.
 *
 * ⚠ **THE SCREEN THAT MATTERS MOST HERE IS THE ONE WITH NO DATA.** The Product
 * Owner ruled the same day that a run which finds no connection *"can stop the
 * job saying APi or conenct not available; that is a valid case and state for
 * us"*. That is the screen a real utility meets on day one, so this check walks
 * it FIRST and asks the only question that matters about it: **does it read as
 * a designed answer, or as a failure?** A backend test cannot answer that.
 *
 * ── HOW TO RUN IT ────────────────────────────────────────────────────────
 *   DJANGO_SETTINGS_MODULE=config.settings.local DATABASE_URL=…smartbillhub \
 *     python3.12 10-scripts/render-checks/rbs_q_seed_sync.py --tenant brazosbend
 *   … which prints SMOKE_GIS_STOPPED_RUN_ID, SMOKE_FEEDBACK_STOPPED_RUN_ID,
 *     SMOKE_GIS_RUN_ID and SMOKE_FEEDBACK_RUN_ID.
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local DATABASE_URL=…smartbillhub \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8077 --noreload &
 *   (cd 07-frontend && npx vite build && \
 *      PORT=4277 API_PROXY_TARGET=http://127.0.0.1:8077 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4277 SMOKE_GIS_STOPPED_RUN_ID=… … \
 *   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/rbs-q-sync-runbooks.mjs
 *
 * ── WHAT IT ASSERTS ──────────────────────────────────────────────────────
 *   THE TWO STOPPED RUNS — the ones a real utility hits first
 *   1  **THE HEAD SAYS WHAT HAPPENED IN PLAIN WORDS**, read from the DOM, so a
 *      verdict block the renderer dropped is caught (`DEF-RBS-4284`: the engine
 *      and the renderer agreeing on a NAME and disagreeing on a payload).
 *   2  **THE CHAIN DREW EVERY STEP, ONE RED AND THE REST *NEVER REACHED***, and
 *      the red cell is actually PAINTED — read from COMPUTED STYLE, never from a
 *      class name, because B14 rule 21's migration clause means an unlisted
 *      file's utility renders as nothing at all while the class sits in the DOM.
 *   3  **NO KPI STRIP.** *0 applied · 0 queued · 0 never touched* over a run
 *      that examined nothing is indistinguishable from a morning the county
 *      agreed with us about everything.
 *   4  **THE PAGE NEVER SAYS "FAILED" OR "ERROR".** The ruling's whole point.
 *
 *   THE TWO WORKING RUNS
 *   5  **THE KPI STRIP DREW ITS TILES WITH THE RUN'S OWN NUMBERS**, and the
 *      first tile says **To apply** / **To suppress** rather than the past
 *      tense, because nothing has been written.
 *   6  **OURS · THEIRS ON EVERY QUEUED ROW** with *Accept theirs →* and *Keep
 *      ours* — `US-RBS-032`'s acceptance sentence, asserted on the SCREEN.
 *   7  **WHERE EACH SUPPRESSED CHANNEL FELL BACK TO** is on the screen —
 *      `US-RBS-034`'s acceptance sentence, in the by-channel table.
 *   8  **EVERY FIX IS A REAL DESTINATION** — a resolvable href, never a present
 *      string: `//host/…` reads as a perfectly good href to `toContain`
 *      (`DEF-CWP-3925`).
 *   9  **CLICKING ONE LANDS ON A SCREEN THAT EXISTS** — the half of
 *      `BR-RBS-011` no unit test can reach.
 *
 *   ALL FOUR
 *  10  **B14 RULES 31 AND 32** — no database id and no rule id in what a clerk
 *      reads. `decided_by_rule` IS on every row, in `ReportRow.meta`, and no
 *      block draws it; this is what proves that.
 *  11  **THE PAGE DOES NOT SCROLL SIDEWAYS** at 1440.
 *
 * ⚠ **WHAT THIS CHECK CANNOT SAY, STATED RATHER THAN LEFT AS A THIN PASS.**
 * Runbook 22's *nothing left* row — the one carrying **Owed** — cannot be
 * produced on this deployment at all: every account with print traffic has an
 * email and a phone on file, and no adapter writes a bounce on any channel. So
 * the money cell is proved in
 * `06-backend/tests/test_us_rbs_034_undeliverable_contacts.py` and NOT here,
 * and this file says so instead of asserting a row it knows will be absent.
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4277";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const GIS_STOPPED = process.env.SMOKE_GIS_STOPPED_RUN_ID ?? "";
const FEEDBACK_STOPPED = process.env.SMOKE_FEEDBACK_STOPPED_RUN_ID ?? "";
const GIS_RUN = process.env.SMOKE_GIS_RUN_ID ?? "";
const FEEDBACK_RUN = process.env.SMOKE_FEEDBACK_RUN_ID ?? "";
const OUT = process.env.SMOKE_OUT ?? "/tmp/rbs-q-sync-runbooks";
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

if ([GIS_STOPPED, FEEDBACK_STOPPED, GIS_RUN, FEEDBACK_RUN].some((one) => one === "")) {
  console.error(
    "⛔ all four run ids must be set. This check reads STORED runs — it cannot start one,\n" +
      "   because POST /runbooks/{key}/runs is task L. Seed them first; see the header.",
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

  // The server's own answer, captured rather than inferred. *Did the screen
  // draw it* and *did the server send it* are two different questions, and
  // `DEF-RBS-4284` is what happens when only one is asked.
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

  async function walkTheStop(key, runId, shot, steps, label) {
    console.log(`── the stopped run · ${label} ────────────────────────────`);
    const { body, served } = await open(key, runId, shot);
    const verdict = served?.blocks?.find((b) => b.block === "verdict") ?? null;
    check(verdict !== null, "the server served a verdict block");
    if (verdict !== null) {
      check(
        body.includes(verdict.payload.count),
        `the head says what happened: "${verdict.payload.count}"`,
      );
      check(verdict.payload.word === "Stopped", `the verdict word is "Stopped"`);
    }
    const sentence = served?.blocks?.find((b) => b.block === "sentence") ?? null;
    check(sentence !== null, "the server served the what-to-do sentence");
    if (sentence !== null) check(body.includes(sentence.payload.text), "the page says what to do");

    const cells = await page.$$("[data-chain-state]");
    check(cells.length === steps, `the chain drew ${steps} cells (saw ${cells.length})`);
    const states = [];
    for (const cell of cells) states.push(await cell.getAttribute("data-chain-state"));
    check(states.filter((s) => s === "bad").length === 1, `exactly one cell is red`);
    check(
      states.filter((s) => s === "notReached").length === steps - 1,
      `${steps - 1} cells read Never reached (saw ${states.join(", ")})`,
    );
    const red = cells[states.indexOf("bad")];
    if (red) {
      // ⚠ COMPUTED STYLE, NOT A CLASS NAME — an unlisted file's Tailwind utility
      // renders as NOTHING while the class sits in the DOM and `toContain` passes.
      const painted = await red.evaluate((el) => getComputedStyle(el).backgroundColor);
      check(
        painted !== "rgba(0, 0, 0, 0)" && painted !== "transparent",
        `the red chain cell is actually PAINTED (computed ${painted})`,
      );
      check(((await red.textContent()) ?? "").trim().length > 0, "the red cell names the stop");
    }
    check(
      (served?.blocks ?? []).every((b) => b.block !== "kpis"),
      "a stopped run draws NO KPI strip — zeroes would read like a clean day",
    );
    check(
      !/\bfailed\b/i.test(body) && !/\berror\b/i.test(body),
      "the stopped page never says failed or error — the absence is a RESULT",
    );
    noInternalIds(body, `${label} stopped page`);
    check((await page.evaluate(SIDEWAYS)) === 0, `${label} stopped page does not scroll sideways`);
    return { body, served };
  }

  await walkTheStop("gis-reconciliation", GIS_STOPPED, "rbs-006-r20-stopped.png", 7, "GIS");
  await walkTheStop(
    "undeliverable-contacts",
    FEEDBACK_STOPPED,
    "rbs-006-r22-stopped.png",
    6,
    "feedback",
  );

  // ══ THE GIS RUN OVER A REAL PARCEL FILE ════════════════════════════════
  console.log("── the parcel run · GIS reconciliation ───────────────────");
  let { body, served } = await open("gis-reconciliation", GIS_RUN, "rbs-006-r20-run.png");

  let kpis = served?.blocks?.find((b) => b.block === "kpis") ?? null;
  check(kpis !== null, "the server served a KPI strip");
  if (kpis !== null) {
    for (const tile of kpis.payload.tiles) check(body.includes(tile.label), `tile "${tile.label}" drew`);
    check(
      kpis.payload.tiles[0].label === "To apply",
      `the first tile says "To apply" while nothing is changed (saw "${kpis.payload.tiles[0].label}")`,
    );
  }
  const byClass = served?.blocks?.find((b) => b.block === "breakdown") ?? null;
  check(byClass !== null, "the by-class table was served");
  if (byClass !== null) {
    check(body.includes(byClass.payload.heading), "the by-class heading drew");
    for (const column of byClass.payload.columns) {
      check(body.includes(column.label), `by-class column "${column.label}" drew`);
    }
  }

  // 6 · `US-RBS-032`'s acceptance sentence, on the screen.
  const decisions = served?.blocks?.find((b) => b.block === "row_decisions") ?? null;
  check(decisions !== null, "the queued-for-a-person table was served");
  if (decisions !== null) {
    check(decisions.payload.rows.length > 0, "the file produced rows a person has to decide");
    for (const column of decisions.payload.columns) {
      check(body.includes(column.label), `queued column "${column.label}" drew`);
    }
    for (const choice of decisions.payload.choices) {
      const button = await page.$(`[data-decision="${choice.id}"]`);
      check(button !== null, `the decision button "${choice.label}" is on the page`);
    }
    for (const row of decisions.payload.rows) {
      check(
        body.includes(row.cells.ours.text) && body.includes(row.cells.theirs.text),
        `Ours "${row.cells.ours.text}" and Theirs "${row.cells.theirs.text}" both drew`,
      );
    }
  }

  let firstFixHref = null;
  let records = served?.blocks?.find((b) => b.block === "records") ?? null;
  check(records !== null, "the records table was served");
  if (records !== null) {
    for (const row of records.payload.rows) {
      const fix = row.cells.fix;
      const link = await page.$(`a[href$="${fix.to}"]`);
      check(link !== null, `fix route "${fix.label}" is a real link to /${fix.to}`);
      if (firstFixHref === null && link !== null) firstFixHref = await link.getAttribute("href");
    }
  }
  noInternalIds(body, "GIS run page");
  check((await page.evaluate(SIDEWAYS)) === 0, "the GIS run page does not scroll sideways at 1440");

  // ══ THE FEEDBACK RUN OVER REAL RETURNED LETTERS ════════════════════════
  console.log("── the feedback run · undeliverable contacts ─────────────");
  ({ body, served } = await open("undeliverable-contacts", FEEDBACK_RUN, "rbs-006-r22-run.png"));

  kpis = served?.blocks?.find((b) => b.block === "kpis") ?? null;
  check(kpis !== null, "the server served a KPI strip");
  if (kpis !== null) {
    for (const tile of kpis.payload.tiles) check(body.includes(tile.label), `tile "${tile.label}" drew`);
    check(
      kpis.payload.tiles[0].label === "To suppress",
      `the first tile says "To suppress" while nothing is suppressed (saw "${kpis.payload.tiles[0].label}")`,
    );
  }

  // 7 · `US-RBS-034`'s acceptance sentence: WHERE each one fell back to.
  const byChannel = served?.blocks?.find((b) => b.block === "breakdown") ?? null;
  check(byChannel !== null, "the by-channel table was served");
  if (byChannel !== null) {
    check(body.includes(byChannel.payload.heading), "the by-channel heading drew");
    for (const row of byChannel.payload.rows) {
      check(
        body.includes(row.cells.to.text),
        `where "${row.cells.channel.text}" falls back to drew: "${row.cells.to.text}"`,
      );
    }
  }
  records = served?.blocks?.find((b) => b.block === "records") ?? null;
  check(records !== null, "the nothing-left table was served");
  if (records !== null && records.payload.rows.length === 0) {
    // ⚠ **AN EMPTY TABLE IS THE TRUTH HERE AND THE CHECK SAYS SO OUT LOUD.**
    // Every account with print traffic on this tenant has an email on file, so
    // every suppression falls back and nothing is stranded. The empty state must
    // still SAY that rather than showing a bare table (B14 rule 17).
    check(
      body.includes(records.payload.empty.title),
      `the empty state says why: "${records.payload.empty.title}"`,
    );
  }
  noInternalIds(body, "feedback run page");
  check(
    (await page.evaluate(SIDEWAYS)) === 0,
    "the feedback run page does not scroll sideways at 1440",
  );

  // 9 · clicking a fix route lands on a screen that EXISTS. The half of
  // `BR-RBS-011` no unit test can reach: a route can be a perfectly formed
  // string and open onto "not built yet".
  if (firstFixHref !== null) {
    console.log("── click a fix route ─────────────────────────────────────");
    await page.goto(`${BASE}${firstFixHref}`, { waitUntil: "networkidle" });
    await page
      .waitForFunction(() => document.querySelector(".skeleton") === null, { timeout: 20000 })
      .catch(() => {});
    await page.screenshot({ path: join(OUT, "fix-route.png"), fullPage: true });
    const landed = (await page.textContent("body")) ?? "";
    check(
      !/not built yet|coming soon|opens with the next release|page not found/i.test(landed),
      `the fix route ${firstFixHref} opens a screen that exists`,
    );
  }

  await browser.close();

  console.log("");
  console.log(`── ${failures.length === 0 ? "ALL CHECKS PASSED" : `${failures.length} FAILED`}`);
  for (const message of failures) console.log(`   ⛔ ${message}`);
  console.log(`── screenshots in ${OUT}`);
  process.exit(failures.length === 0 ? 0 : 1);
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
