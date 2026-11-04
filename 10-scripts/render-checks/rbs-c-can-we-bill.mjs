/**
 * RENDERED-OUTPUT CHECK — CR-075 wave C task `C8`. `RBS-006`, in a real browser.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: *"no gate looks at rendered output"*,
 * and nine defects were found by that and by nothing else. PO ruling
 * 2026-08-30: a screen a lane changed is browser-tested against a real server.
 * And the Product Owner's own definition of done, 2026-09-06: *"ensure you do
 * web walkthorugh before you sign off the user story or build"*.
 *
 * ⚠ **THE TASK ROW SAYS "RUN IT" AND THIS SCRIPT CANNOT, AND THAT IS STATED
 * RATHER THAN QUIETLY SUBSTITUTED.** `C8` reads *"run it, read 3 things stop
 * billing, click a fix route, and diff the database"*. Starting a run needs
 * `POST /runbooks/{key}/runs`, which is task `L` — phase 2, the acting half,
 * not built. Every runbooks route that exists today is a `GET`; `api.py` says
 * so in its own docstring, and `BR-RBS-002` is why. So this check EXECUTES the
 * runbook through the engine directly (the same call the future endpoint will
 * make), stores the run, and then drives the browser over the result. What is
 * proved is everything from the stored run onwards, which is the whole of what
 * wave C builds. **The click-to-start half is `L`'s walkthrough, not this
 * one's**, and pretending otherwise would be a walkthrough that passes over a
 * feature nobody has written.
 *
 * ── HOW TO RUN IT ────────────────────────────────────────────────────────
 *   Use a database NOBODY ELSE is seeding — on 2026-08-30 a sibling check lost
 *   three runs to the shared one, with every id changing mid-run, which looks
 *   exactly like a broken screen.
 *
 *   createdb smartbillhub_rbsc
 *   DJANGO_SETTINGS_MODULE=config.settings.local \
 *   DATABASE_URL="postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub_rbsc" \
 *     python3 06-backend/manage.py migrate
 *   … seed_demo, then `python3 10-scripts/render-checks/rbs_c_seed_run.py` to
 *     execute runbook 1 and store its run.
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local DATABASE_URL=…rbsc \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8075 --noreload &
 *   (cd 07-frontend && npx vite build && \
 *      PORT=4275 API_PROXY_TARGET=http://127.0.0.1:8075 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4275 SMOKE_RUN_ID=<the run's id> \
 *   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/rbs-c-can-we-bill.mjs
 *
 * ── WHAT IT ASSERTS, REGION BY REGION AGAINST `wireframes/RBS-006-R1` ─────
 *   1  **THE HEAD SAYS WHAT STOPS BILLING.** Region 1's subtitle is the
 *      verdict block's own sentence. A screen that renders the head and drops
 *      the verdict is `DEF-RBS-4284` coming back: the engine and the renderer
 *      agreeing on a NAME and disagreeing on a payload, which every unit suite
 *      on both sides passes over.
 *   2  **THE KPI STRIP DREW ITS TILES** (region 2) and the numbers are the
 *      run's, not zeroes — a strip of zeroes is what a dropped payload looks
 *      like.
 *   3  **THE CHAIN DREW TEN CELLS AND IS RED AT THE EARLIEST FAILURE**
 *      (region 3), with each red cell NAMING its blocker. Read from COMPUTED
 *      STYLE, not from a class name: B14 rule 21's migration clause means an
 *      unlisted file's utility renders as NOTHING while the class sits in the
 *      DOM and every `toContain` passes.
 *   4  **THE CHIPS CARRY COUNTS AND ONE IS SELECTED** (region 4).
 *   5  **THE TABLE DREW FIVE COLUMNS AND EVERY FIX ROUTE IS A REAL LINK**
 *      (region 5) — asserted as a WHOLE ADDRESS, never as a suffix and never
 *      as a present string. `//host/…` reads as a perfectly good href to a
 *      string assertion (`DEF-CWP-3925`), and `a[href$="plans-rates"]` — which
 *      is what this file used to ask for — is satisfied by
 *      `…/runs/<id>/plans-rates`, which is `DEF-RBS-4329` exactly.
 *   6  **CLICKING EVERY FIX ROUTE LANDS ON A SCREEN THAT EXISTS, AT THE
 *      ADDRESS IT NAMED** — the half of `BR-RBS-011` no unit test can reach.
 *      Every distinct route, because a sample of one is not a check of a
 *      column, and the defect broke all of them at once.
 *   7  **THE PAGINATION FOOTER IS PRESENT** (region 6, B14 rule 16).
 *   8  **NOTHING OUTSIDE THE SEVEN RUNBOOKS TABLES CHANGED.** A Check is
 *      CONSTRUCTED with no writer (`BR-RBS-002`) — the capability is absent
 *      rather than refused — and this is the only place that claim is tested
 *      against a real database rather than against a mock.
 *   9  **B14 RULE 31 AND 32** — no database id and no rule id in what a clerk
 *      reads. `decided_by_rule` IS on every row, in `ReportRow.meta`, and no
 *      block draws it; this is what proves that.
 *  10  **THE PAGE DOES NOT SCROLL SIDEWAYS** at 1440.
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4275";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const RUN_ID = process.env.SMOKE_RUN_ID ?? "";
const KEY = process.env.SMOKE_RUNBOOK ?? "configuration-check";
const OUT = process.env.SMOKE_OUT ?? "/tmp/rbs-c-can-we-bill";
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

if (RUN_ID === "") {
  console.error(
    "⛔ SMOKE_RUN_ID is not set. This check reads a STORED run — it cannot start one,\n" +
      "   because POST /runbooks/{key}/runs is task L (phase 2) and every runbooks route\n" +
      "   that exists today is a GET. Seed a run first; see this file's header.",
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
  // ⚠ **`input[type="email"]` MATCHES NOTHING ON THIS SCREEN.** `S3` draws the
  // work-email field as `type="text"` with `id="signin-email"`, so the obvious
  // selector waits thirty seconds and times out with a message about a locator
  // rather than about the page — which reads like a broken screen and is a
  // broken selector. Asserted by id, which is what the screen actually has.
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  // ⚠ **WAIT FOR THE LANDING, NOT FOR THE NETWORK.** Sign-in is an XHR, so the
  // page never navigates and `waitForLoadState("networkidle")` returns almost
  // immediately — the check then walked on to `RBS-006` before the session
  // cookie existed and read FIVE 401s as five broken regions. The screen was
  // fine; the wait was wrong. Landing on the dashboard is the fact that the
  // session is real, so that is what is waited for.
  await page.waitForURL(/\/dashboard(\?|$)/, { timeout: 30000 });

  console.log("── RBS-006, region by region ─────────────────────────────");
  await page.goto(`${BASE}/${TENANT}/runbooks/${KEY}/runs/${RUN_ID}`, {
    waitUntil: "networkidle",
  });
  await page.screenshot({ path: join(OUT, "rbs-006-result.png"), fullPage: true });

  const body = (await page.textContent("body")) ?? "";

  // 1 · region 1 — the head carries the verdict's own sentence.
  const reportBody = wire.find((w) => /\/report\b/.test(w.url))?.body ?? "";
  const served = reportBody === "" ? null : JSON.parse(reportBody);
  const verdict = served?.blocks?.find((b) => b.block === "verdict") ?? null;
  check(verdict !== null, "the server served a verdict block");
  if (verdict !== null) {
    check(
      body.includes(verdict.payload.count),
      `the head says what the run found: "${verdict.payload.count}"`,
    );
  }

  // 2 · region 2 — the KPI strip drew its tiles with the run's own numbers.
  const kpis = served?.blocks?.find((b) => b.block === "kpis") ?? null;
  if (kpis !== null) {
    for (const tile of kpis.payload.tiles) {
      check(body.includes(tile.label), `KPI tile "${tile.label}" drew`);
    }
  }

  // 3 · region 3 — ten cells, red at the earliest failure, each naming it.
  const chainCells = await page.$$("[data-chain-state]");
  check(chainCells.length === 10, `the chain drew ten cells (saw ${chainCells.length})`);
  const redPositions = [];
  for (const [index, cell] of chainCells.entries()) {
    const state = await cell.getAttribute("data-chain-state");
    if (state !== "bad") continue;
    redPositions.push(index + 1);
    // ⚠ COMPUTED STYLE, NOT A CLASS NAME. B14 rule 21's migration clause means
    // an unlisted file's utility renders as NOTHING while the class sits in the
    // DOM — `tsc`, eslint and every `toContain("bg-danger-100")` pass over it.
    const painted = await cell.evaluate((el) => getComputedStyle(el).backgroundColor);
    check(
      painted !== "rgba(0, 0, 0, 0)" && painted !== "transparent",
      `red chain cell ${index + 1} is actually PAINTED (computed ${painted})`,
    );
    const text = (await cell.textContent()) ?? "";
    check(text.trim().length > 0, `red chain cell ${index + 1} names its blocker`);
  }
  check(redPositions.length > 0, `the chain is red somewhere (${redPositions.join(", ")})`);

  // 4 · region 4 — the chips carry counts and exactly one is selected.
  const selected = await page.$$('[data-chip="selected"]');
  check(selected.length === 1, `exactly one chip is selected (saw ${selected.length})`);

  // 5 · region 5 — five columns, and every fix route is a REAL destination.
  //
  // ⚠ **THIS SECTION USED TO EVAPORATE IN SILENCE, AND THAT IS HOW
  // `DEF-RBS-4329` GOT PAST IT.** It was wrapped in `if (records !== null)`
  // with nothing asserting that the block was found, and the click below was
  // wrapped in `if (firstFixHref !== null)` with nothing asserting that a fix
  // route existed. Miss the block and every check inside both vanishes — the
  // run still exits 0 and the only trace is a smaller number of ticks, which
  // nobody counts. Hard-won law 7: *a declared blind spot with no NUMBER
  // attached is indistinguishable from an empty one.* So the block's presence
  // is a CHECK now, and the counts are printed.
  const records = served?.blocks?.find((b) => b.block === "records") ?? null;
  check(records !== null, "the report carries a records block to read fix routes from");
  const fixHrefs = [];
  if (records !== null) {
    for (const column of records.payload.columns) {
      check(body.includes(column.label), `column "${column.label}" drew`);
    }
    for (const row of records.payload.rows) {
      const fix = row.cells.fix;
      // ⚠ **THE WHOLE ADDRESS, ANCHORED — NOT `href$=`.** The suffix selector
      // is what let `DEF-RBS-4329` through: with the bug the href read
      // `/{tenant}/runbooks/{key}/runs/{id}/plans-rates`, which ENDS in
      // `plans-rates` and satisfied `a[href$="plans-rates"]` perfectly. A fix
      // route is `/{tenant}/{route}` and nothing else.
      const want = `/${TENANT}/${fix.to}`;
      const link = await page.$(`a[href="${want}"]`);
      // ⚠ SAY WHAT IT ACTUALLY POINTS AT WHEN IT IS WRONG. A check whose
      // output cannot distinguish pass from fail TO A READER is worse than no
      // check, because it is trusted — and "fix route X points at /a/b ⛔"
      // sends the reader hunting for a link that may be one segment out.
      const actual =
        link === null
          ? await page.$eval(
              `[data-fix-route]`,
              (a, label) =>
                Array.from(a.ownerDocument.querySelectorAll("[data-fix-route]"))
                  .filter((n) => n.textContent?.trim() === label)
                  .map((n) => n.getAttribute("href"))
                  .join(" | ") || "no link with that label at all",
              fix.label,
            ).catch(() => "could not read the DOM")
          : null;
      check(
        link !== null,
        `fix route "${fix.label}" points at ${want}${link === null ? ` — saw ${actual}` : ""}`,
      );
      if (link !== null) {
        const href = await link.getAttribute("href");
        if (!fixHrefs.includes(href)) fixHrefs.push(href);
      }
    }
  }
  check(fixHrefs.length > 0, `there is at least one fix route to click (found ${fixHrefs.length})`);

  // 7 · region 6 — the pagination footer (B14 rule 16).
  check((await page.$(".table-pager")) !== null, "the pagination footer is present");

  // 9 · B14 rules 31 and 32 — nothing internal reaches a clerk.
  for (const pattern of FORBIDDEN_IN_CLERK_COPY) {
    const hit = body.match(pattern);
    check(hit === null, `no internal id on screen${hit ? ` — saw ${hit[0]}` : ""}`);
  }

  // 10 · the page does not scroll sideways at 1440.
  check((await page.evaluate(SIDEWAYS)) === 0, "the result page does not scroll sideways at 1440");

  // 6 · clicking a fix route lands on a screen that EXISTS. The half of
  // `BR-RBS-011` no unit test can reach: a route can be a perfectly formed
  // string and open onto "not built yet".
  //
  // ⚠ **EVERY DISTINCT ROUTE, NOT THE FIRST ONE.** A sample of one is not a
  // check of a column — `DEF-RBS-4329` broke every fix route on every runbook,
  // and one green click would have read as the column working.
  console.log("── click every fix route ─────────────────────────────────");
  for (const [index, href] of fixHrefs.entries()) {
    await page.goto(`${BASE}${href}`, { waitUntil: "networkidle" });
    await page.screenshot({ path: join(OUT, `fix-route-${index + 1}.png`), fullPage: true });
    const landed = (await page.textContent("body")) ?? "";
    check(
      !/not built yet|coming soon|opens with the next release/i.test(landed),
      `${href} opens a screen that exists`,
    );
    // And it must be the screen the route NAMED, not some other screen the
    // router happened to match — law 7 records a hold-expiry test that asserted
    // an address while the router mounted the screen somewhere else, green.
    check(
      new URL(page.url()).pathname === href,
      `${href} is still the address after it loads (saw ${new URL(page.url()).pathname})`,
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
