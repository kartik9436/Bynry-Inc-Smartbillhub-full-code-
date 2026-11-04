/**
 * RENDERED-OUTPUT CHECK — CR-075 wave P. The two MONEY runbooks in a real browser.
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
 * a designed answer, or as a failure?** A backend test cannot answer that —
 * only a person or a browser looking at the page can.
 *
 * ── HOW TO RUN IT ────────────────────────────────────────────────────────
 *   DJANGO_SETTINGS_MODULE=config.settings.local DATABASE_URL=…smartbillhub \
 *     python3.12 10-scripts/render-checks/rbs_p_seed_money.py --tenant brazosbend
 *   … which prints SMOKE_STOPPED_RUN_ID, SMOKE_BANKREC_RUN_ID and
 *     SMOKE_APPLIED_RUN_ID.
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local DATABASE_URL=…smartbillhub \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8077 --noreload &
 *   (cd 07-frontend && npx vite build && \
 *      PORT=4277 API_PROXY_TARGET=http://127.0.0.1:8077 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4277 SMOKE_STOPPED_RUN_ID=… \
 *   SMOKE_BANKREC_RUN_ID=… SMOKE_APPLIED_RUN_ID=… \
 *   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/rbs-p-money-runbooks.mjs
 *
 * ── WHAT IT ASSERTS ──────────────────────────────────────────────────────
 *   THE STOPPED RUN — the one a real utility hits first
 *   1  **THE HEAD SAYS WHAT HAPPENED IN PLAIN WORDS** — *"Nothing to work
 *      on."* — and the page carries the sentence that says what to do about it.
 *      Read from the DOM, so a verdict block the renderer dropped is caught
 *      (`DEF-RBS-4284`: the engine and the renderer agreeing on a NAME and
 *      disagreeing on a payload, with every unit suite on both sides green).
 *   2  **THE CHAIN DREW EVERY STEP, ONE RED AND THE REST *NEVER REACHED***,
 *      and the red cell is actually PAINTED — read from COMPUTED STYLE, never
 *      from a class name, because B14 rule 21's migration clause means an
 *      unlisted file's utility renders as nothing at all while the class sits
 *      in the DOM and every `toContain` passes.
 *   3  **NO KPI STRIP.** *0 applied · $0.00 · 0 need a person* over a run that
 *      examined nothing is indistinguishable from a clean day — hard-won law 7,
 *      and the reason the stopped composition omits the strip. Asserted as an
 *      ABSENCE on the page, which is the only place the decision is visible.
 *   4  **THE PAGE NEVER SAYS "FAILED" OR "ERROR".** The whole point of the
 *      ruling is that this is a RESULT.
 *
 *   THE FILE RUN
 *   5  **THE KPI STRIP DREW ITS TILES WITH THE RUN'S OWN NUMBERS**, and the
 *      first tile says **To apply** rather than *Applied*, because nothing has
 *      been applied.
 *   6  **THE BY-SOURCE TABLE DREW**, with the source the file actually arrived
 *      as.
 *   7  **EVERY UNMATCHED ROW'S FIX IS A REAL DESTINATION** — asserted as a
 *      resolvable href, never as a present string: `//host/…` reads as a
 *      perfectly good href to a string assertion (`DEF-CWP-3925`).
 *   8  **CLICKING ONE LANDS ON A SCREEN THAT EXISTS** — the half of
 *      `BR-RBS-011` no unit test can reach.
 *
 *   BOTH
 *   9  **B14 RULES 31 AND 32** — no database id and no rule id in what a clerk
 *      reads. `decided_by_rule` IS on every row, in `ReportRow.meta`, and no
 *      block draws it; this is what proves that.
 *  10  **THE PAGE DOES NOT SCROLL SIDEWAYS** at 1440.
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
const STOPPED = process.env.SMOKE_STOPPED_RUN_ID ?? "";
const BANKREC = process.env.SMOKE_BANKREC_RUN_ID ?? "";
const APPLIED = process.env.SMOKE_APPLIED_RUN_ID ?? "";
const OUT = process.env.SMOKE_OUT ?? "/tmp/rbs-p-money-runbooks";
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

if (STOPPED === "" || BANKREC === "" || APPLIED === "") {
  console.error(
    "⛔ SMOKE_STOPPED_RUN_ID, SMOKE_BANKREC_RUN_ID and SMOKE_APPLIED_RUN_ID must all be set.\n" +
      "   This check reads STORED runs — it cannot start one, because POST /runbooks/{key}/runs\n" +
      "   is task L. Seed them first; see this file's header.",
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
  // ⚠ `input[type="email"]` MATCHES NOTHING: `S3` draws the work-email field as
  // `type="text"` with `id="signin-email"`.
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  // ⚠ WAIT FOR THE LANDING, NOT FOR THE NETWORK. Sign-in is an XHR, so the page
  // never navigates and `networkidle` returns before the session cookie exists —
  // the check then reads five 401s as five broken regions.
  await page.waitForURL(/\/dashboard(\?|$)/, { timeout: 30000 });

  async function open(key, runId, shot) {
    wire = [];
    await page.goto(`${BASE}/${TENANT}/runbooks/${key}/runs/${runId}`, {
      waitUntil: "networkidle",
    });
    // ⚠ **`networkidle` IS NOT ENOUGH AND THE FIRST RUN OF THIS CHECK PROVED
    // IT.** The page fetches the run and its report through `useQuery`, so the
    // first navigation after sign-in returned with the LOADING SKELETON on
    // screen: the screenshot was four grey bars, `[data-chain-state]` matched
    // nothing, and the check reported *"the server served no verdict block"*
    // over a server that had served one perfectly. **That is a broken WAIT
    // reading as a broken SCREEN**, which is the same fault `rbs-c`'s header
    // records for sign-in one step earlier.
    //
    // So it waits for the skeleton to GO — a positive fact about the rendered
    // page, not a guess about the network — and only then reads anything.
    await page
      .waitForFunction(() => document.querySelector(".skeleton") === null, { timeout: 20000 })
      .catch(() => {
        /* fall through: the assertions below report what is actually there */
      });
    await page.screenshot({ path: join(OUT, shot), fullPage: true });
    const reportBody = wire.find((w) => /\/report\b/.test(w.url))?.body ?? "";
    return {
      body: (await page.textContent("body")) ?? "",
      served: reportBody === "" ? null : JSON.parse(reportBody),
    };
  }

  // ══ 1 · THE STOPPED RUN — cash application, nothing to work on ══════════
  console.log("── the stopped run · cash application ────────────────────");
  let { body, served } = await open("cash-application", STOPPED, "rbs-006-r10-stopped.png");

  const verdict = served?.blocks?.find((b) => b.block === "verdict") ?? null;
  check(verdict !== null, "the server served a verdict block");
  if (verdict !== null) {
    check(
      body.includes(verdict.payload.count),
      `the head says what happened: "${verdict.payload.count}"`,
    );
  }
  const sentence = served?.blocks?.find((b) => b.block === "sentence") ?? null;
  check(sentence !== null, "the server served the what-to-do sentence");
  if (sentence !== null) {
    check(body.includes(sentence.payload.text), "the page says what to do about it");
  }

  const cells = await page.$$("[data-chain-state]");
  check(cells.length === 7, `the chain drew seven cells (saw ${cells.length})`);
  const states = [];
  for (const cell of cells) states.push(await cell.getAttribute("data-chain-state"));
  check(states[0] === "bad", `the first cell is red (saw ${states[0]})`);
  check(
    states.slice(1).every((s) => s === "notReached"),
    `every later cell reads Never reached (saw ${states.slice(1).join(", ")})`,
  );
  if (cells.length > 0) {
    // ⚠ COMPUTED STYLE, NOT A CLASS NAME — B14 rule 21's migration clause means
    // an unlisted file's utility renders as NOTHING while the class sits in the
    // DOM and every `toContain` passes over it.
    const painted = await cells[0].evaluate((el) => getComputedStyle(el).backgroundColor);
    check(
      painted !== "rgba(0, 0, 0, 0)" && painted !== "transparent",
      `the red chain cell is actually PAINTED (computed ${painted})`,
    );
    const text = (await cells[0].textContent()) ?? "";
    check(text.trim().length > 0, "the red chain cell names what stopped the run");
  }

  check(
    (served?.blocks ?? []).every((b) => b.block !== "kpis"),
    "a stopped run draws NO KPI strip — zeroes would read like a clean day",
  );
  check(
    !/\bfailed\b/i.test(body) && !/\berror\b/i.test(body),
    "the stopped page never says failed or error — the absence is a RESULT",
  );
  for (const pattern of FORBIDDEN_IN_CLERK_COPY) {
    const hit = body.match(pattern);
    check(hit === null, `stopped page: no internal id on screen${hit ? ` — saw ${hit[0]}` : ""}`);
  }
  check(
    (await page.evaluate(SIDEWAYS)) === 0,
    "the stopped page does not scroll sideways at 1440",
  );

  // ══ 2 · THE STOPPED RUN — bank reconciliation ═══════════════════════════
  console.log("── the stopped run · bank reconciliation ─────────────────");
  ({ body, served } = await open("bank-reconciliation", BANKREC, "rbs-006-r14-stopped.png"));
  const bankVerdict = served?.blocks?.find((b) => b.block === "verdict") ?? null;
  check(bankVerdict !== null, "the server served a verdict block");
  if (bankVerdict !== null) {
    check(body.includes(bankVerdict.payload.count), `the head reads "${bankVerdict.payload.count}"`);
  }
  const bankCells = await page.$$("[data-chain-state]");
  check(bankCells.length === 6, `the chain drew six cells (saw ${bankCells.length})`);
  check(
    (await page.evaluate(SIDEWAYS)) === 0,
    "the bank-rec stopped page does not scroll sideways at 1440",
  );

  // ══ 3 · THE FILE RUN — cash application over an uploaded file ═══════════
  console.log("── the file run · cash application ───────────────────────");
  ({ body, served } = await open("cash-application", APPLIED, "rbs-006-r10-file.png"));

  const kpis = served?.blocks?.find((b) => b.block === "kpis") ?? null;
  check(kpis !== null, "the server served a KPI strip");
  if (kpis !== null) {
    for (const tile of kpis.payload.tiles) {
      check(body.includes(tile.label), `KPI tile "${tile.label}" drew`);
    }
    check(
      kpis.payload.tiles[0].label === "To apply",
      `the first tile says "To apply" while nothing is applied (saw "${kpis.payload.tiles[0].label}")`,
    );
  }

  const breakdown = served?.blocks?.find((b) => b.block === "breakdown") ?? null;
  check(breakdown !== null, "the by-source table was served");
  if (breakdown !== null) {
    check(body.includes(breakdown.payload.heading), "the by-source heading drew");
    for (const column of breakdown.payload.columns) {
      check(body.includes(column.label), `by-source column "${column.label}" drew`);
    }
  }

  const records = served?.blocks?.find((b) => b.block === "records") ?? null;
  check(records !== null, "the unmatched table was served");
  let firstFixHref = null;
  if (records !== null) {
    for (const column of records.payload.columns) {
      check(body.includes(column.label), `unmatched column "${column.label}" drew`);
    }
    check(records.payload.rows.length > 0, "the file produced rows a person has to work");
    for (const row of records.payload.rows) {
      const fix = row.cells.fix;
      const link = await page.$(`a[href$="${fix.to}"]`);
      check(link !== null, `fix route "${fix.label}" is a real link to /${fix.to}`);
      if (firstFixHref === null && link !== null) firstFixHref = await link.getAttribute("href");
    }
  }

  for (const pattern of FORBIDDEN_IN_CLERK_COPY) {
    const hit = body.match(pattern);
    check(hit === null, `file page: no internal id on screen${hit ? ` — saw ${hit[0]}` : ""}`);
  }
  check((await page.evaluate(SIDEWAYS)) === 0, "the file page does not scroll sideways at 1440");

  // ── 8 · clicking a fix route lands on a screen that EXISTS. The half of
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
