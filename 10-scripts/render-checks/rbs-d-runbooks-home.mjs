/**
 * RENDERED-OUTPUT CHECK — CR-075 wave D task `D2`. `RBS-001`, in a real browser.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: *"no gate looks at rendered output"*,
 * and nine defects were found by that and by nothing else. And the Product
 * Owner's own definition of done, 2026-09-06: *"ensure you do web walkthorugh
 * before you sign off the user story or build"*.
 *
 * ── HOW TO RUN IT ────────────────────────────────────────────────────────
 *   Use a database NOBODY ELSE is seeding — on 2026-08-30 a sibling check lost
 *   three runs to the shared one, with every id changing mid-run, which looks
 *   exactly like a broken screen.
 *
 *     createdb smartbillhub_rbsd2
 *     DJANGO_SETTINGS_MODULE=config.settings.local \
 *     DATABASE_URL="postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub_rbsd2" \
 *       python3.12 06-backend/manage.py migrate && … manage.py seed_demo
 *     … then `python3.12 10-scripts/render-checks/rbs_d2_seed_home.py`, which
 *       prints the ids and the totals this check reads back.
 *
 *     DJANGO_SETTINGS_MODULE=config.settings.local DATABASE_URL=…rbsd2 \
 *       python3.12 06-backend/manage.py runserver 127.0.0.1:8091 --noreload &
 *     (cd 07-frontend && npx vite build && \
 *        PORT=4291 API_PROXY_TARGET=http://127.0.0.1:8091 node server.mjs &)
 *     SMOKE_BASE=http://127.0.0.1:4291 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *       node 10-scripts/render-checks/rbs-d-runbooks-home.mjs
 *
 * ⚠ **THREE THINGS THAT EACH COST A LANE A DEBUGGING CYCLE, WRITTEN DOWN SO
 * THEY COST THE NEXT ONE NONE.** Sign-in is at `/{tenant}/signin`, not
 * `/sign-in`; the work-email field is `#signin-email` and is `type="text"`, so
 * `input[type=email]` matches nothing and times out with a message about a
 * locator rather than about the page; and sign-in is an XHR, so
 * `waitForLoadState("networkidle")` returns before the session cookie exists
 * and every later call answers 401. **Wait for the dashboard URL.**
 *
 * ── WHAT IT ASSERTS, REGION BY REGION AGAINST `wireframes/RBS-001.1`–`.3` ──
 *   0  **THE DOOR.** The rail's **Runbooks** word is CLICKED, and the screen it
 *      opens is `RBS-001`. That is hard-won law 2's mirror asked in a browser:
 *      `DEF-CWP-3925` shipped a front page with two working doors out of eight
 *      and every unit check green, because each wave tested its own screen at
 *      its own address and *has the door started pointing at it* belonged to
 *      nobody.
 *   1  **REGION 1** — kicker, title and subtitle verbatim; three `Verb →`
 *      actions in the frame's order; *Templates →* a LINK whose href RESOLVES
 *      to `RBS-002`, the other two disabled with their reason on `title`.
 *   2  **REGION 2** — four KPI tiles with the frame's labels, and the two with
 *      no source drawing a dash and *Not counted yet.* The two that ARE served
 *      are compared against the SERVER'S OWN `count`, captured off the wire —
 *      *"did the screen draw it"* and *"did the server send it"* are two
 *      different questions and `DEF-RBS-4284` is what happens when only one is
 *      asked.
 *   3  **REGIONS 3 and 5** — two section headings, *Needs you* ABOVE *Finished
 *      recently*, which is `08-screen-layouts.md`'s own design fact.
 *   4  **REGIONS 4 and 6** — the two tables' columns in the sheet's order, and
 *      the awaiting-approval run drawn with its pill.
 *   5  **REGION 7 ×2** — B14 rule 16's footer under BOTH tables. The sheet
 *      draws one; the RULE wins and the divergence is stamped.
 *   6  **`RBS-001.3`** — the in-flight banner, its **Watch →** clicked through
 *      to a run that opens, and **Stop** disabled in the DANGER tier read from
 *      COMPUTED STYLE, never from a class name (B14 rule 21's migration clause
 *      means an unlisted file's utility renders as NOTHING while the class sits
 *      in the DOM and every `toContain` passes).
 *   7  **B14 RULES 31 AND 32** — no uuid, no screen id, no rule or defect
 *      number in what a clerk reads.
 *   8  **THE PAGE DOES NOT SCROLL SIDEWAYS** at 1440.
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4291";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SMOKE_OUT ?? "/tmp/rbs-d-runbooks-home";
const VIEWPORT = { width: 1440, height: 1100 };

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
  /\b(?:OQ|DEF|TC|US|EP|GT|RB|CR)-(?:[A-Z]{3}-)?\d{2,5}\b/,
  /\bRBS-\d{3}\b/,
  /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
];

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });

  // The SERVER's own answers, captured rather than inferred. "Did the screen
  // draw it" and "did the server send it" are two different questions
  // (DEF-RBS-4284).
  const wire = [];
  page.on("response", async (response) => {
    if (!/\/runbooks\b/.test(response.url())) return;
    try {
      wire.push({ url: response.url(), body: await response.text() });
    } catch {
      /* a redirect or a bodyless response has nothing to read */
    }
  });
  const served = (match) => {
    const hit = wire.filter((w) => match.test(w.url)).pop();
    if (hit === undefined) return null;
    try {
      return JSON.parse(hit.body);
    } catch {
      return null;
    }
  };

  console.log("── sign in ───────────────────────────────────────────────");
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/dashboard(\?|$)/, { timeout: 30000 });

  console.log("── 0 · THE DOOR — the rail's Runbooks word is CLICKED ─────");
  // ⚠ WAIT FOR IT, DO NOT COUNT IT. The first draft called `.count()` the
  // instant the dashboard URL settled and got 0 — while the very next line's
  // `.click()` worked, because Playwright's click waits and `count()` does not.
  // A check that races the thing it is checking reports a failure that is not
  // there, which is worse than no check: it teaches the reader to ignore it.
  const railLink = page.locator('aside a[href$="/runbooks"]').first();
  await railLink.waitFor({ timeout: 30000 });
  check((await railLink.count()) > 0, "the rail carries a Runbooks item pointing at /runbooks");
  await railLink.click();
  await page.waitForURL(new RegExp(`/${TENANT}/runbooks$`), { timeout: 30000 });
  await page.waitForSelector('[data-screen="RBS-001"]', { timeout: 30000 });
  check(true, "clicking Runbooks on the rail opens RBS-001 — the door works");
  check(
    (await page.locator('[data-not-built-yet="true"]').count()) === 0,
    "and it is NOT the not-built-yet screen (the hold is released)",
  );
  // ⚠ **TWO SCREENSHOTS, AND THE FIRST ONE FOUND A DEFECT.** `first-paint` is
  // taken the instant the screen id appears — before any read has answered —
  // and it is what showed `DEF-RBS-4333`: the KPI strip printing a confident
  // `0` under *Waiting for you* over a tenant with a run waiting. Every
  // Playwright locator below AUTO-WAITS, so no assertion in this file could
  // ever have seen it; a person opening the picture did. Keep both.
  await page.screenshot({ path: join(OUT, "rbs-001-first-paint.png"), fullPage: true });
  await page.waitForSelector('[data-screen="RBS-001"] table tbody tr', { timeout: 30000 });
  await page.screenshot({ path: join(OUT, "rbs-001-populated.png"), fullPage: true });

  const root = page.locator('[data-screen="RBS-001"]');
  const bodyText = (await root.innerText()) ?? "";

  console.log("── 1 · region 1 — the page head ───────────────────────────");
  // ⚠ `innerText` RETURNS WHAT IS ON SCREEN, AND `.kicker` IS `text-transform:
  // uppercase` — so the rendered string is OPERATIONS and a case-sensitive
  // check fails over a correct screen. That is the right way round for a
  // rendered-output check (`textContent` would have hidden the transform), and
  // it is compared case-insensitively rather than by hard-coding the shouting.
  check(
    bodyText.toLowerCase().includes("operations"),
    'the kicker reads "Operations" (rendered uppercase by .kicker)',
  );
  check(
    (await page.locator('[data-screen="RBS-001"] h1').innerText()).trim() === "Runbooks",
    'the title reads "Runbooks"',
  );
  check(
    bodyText.includes("Checks report. Actions send."),
    'the subtitle reads "Checks report. Actions send."',
  );

  const actionLabels = await root
    .locator("[data-open], [data-held]")
    .evaluateAll((nodes) => nodes.map((n) => n.textContent.trim()));
  check(
    JSON.stringify(actionLabels) ===
      JSON.stringify(["Templates →", "History →", "Work list →"]),
    `three actions in the frame's order: ${JSON.stringify(actionLabels)}`,
  );

  const templates = root.locator('[data-open="templates"]');
  const templatesHref = await templates.getAttribute("href");
  check(
    templatesHref === `/${TENANT}/runbooks/templates`,
    `Templates → is a real link to ${templatesHref}`,
  );
  for (const id of ["history", "workList"]) {
    const held = root.locator(`[data-held="${id}"]`);
    check(await held.isDisabled(), `${id} is disabled — its screen is not built`);
    check(
      (await held.getAttribute("title")) === "Not built yet.",
      `${id} says WHY it is disabled (BR-SHL-025), in three words (B14 rule 33)`,
    );
  }

  console.log("── 2 · region 2 — the KPI strip of four ───────────────────");
  const kpiLabels = await root
    .locator(".kpi .k")
    .evaluateAll((nodes) => nodes.map((n) => n.textContent.trim()));
  check(
    JSON.stringify(kpiLabels) ===
      JSON.stringify(["Block billing", "Waiting for you", "Running now", "Ran clean today"]),
    `four tiles with the frame's labels: ${JSON.stringify(kpiLabels)}`,
  );
  const kpiValues = await root
    .locator(".kpi .v")
    .evaluateAll((nodes) => nodes.map((n) => n.textContent.trim()));
  check(kpiValues[0] === "—", "Block billing draws a DASH, not a confident zero");
  check(kpiValues[3] === "—", "Ran clean today draws a DASH, not a confident zero");
  check(
    (await root.locator("text=Not counted yet.").count()) === 2,
    "and both say so IN THE PAGE, not only in a tooltip (DEF-SHL-4043)",
  );

  // The two that ARE served, against the server's own count.
  const awaiting = served(/f\.outcome=awaiting_approval/);
  const running = served(/f\.outcome=running/);
  check(awaiting !== null, "the server answered the awaiting-approval read");
  check(running !== null, "the server answered the running read");
  if (awaiting !== null) {
    check(
      kpiValues[1] === String(awaiting.count),
      `Waiting for you draws the SERVER's count: screen ${kpiValues[1]} · wire ${awaiting.count}`,
    );
  }
  if (running !== null) {
    check(
      kpiValues[2] === String(running.count),
      `Running now draws the SERVER's count: screen ${kpiValues[2]} · wire ${running.count}`,
    );
  }

  console.log("── 3 · regions 3 and 5 — the two section headings ─────────");
  const headings = await root
    .locator("h5")
    .evaluateAll((nodes) => nodes.map((n) => n.textContent.trim()));
  check(
    JSON.stringify(headings) === JSON.stringify(["Needs you", "Finished recently"]),
    `Needs you sits ABOVE Finished recently: ${JSON.stringify(headings)}`,
  );

  console.log("── 4 · regions 4 and 6 — the two tables ───────────────────");
  const tables = root.locator("table");
  check((await tables.count()) === 2, `two tables drawn (${await tables.count()})`);
  const needsCols = await tables
    .nth(0)
    .locator("thead th")
    .evaluateAll((nodes) => nodes.map((n) => n.textContent.replace(/[⇅↑↓]/g, "").trim()));
  check(
    JSON.stringify(needsCols.slice(0, 5)) ===
      JSON.stringify(["Run", "State", "Detail", "Started", "Actions"]),
    `Needs you columns in the sheet's order: ${JSON.stringify(needsCols.slice(0, 5))}`,
  );
  const finishedCols = await tables
    .nth(1)
    .locator("thead th")
    .evaluateAll((nodes) => nodes.map((n) => n.textContent.replace(/[⇅↑↓]/g, "").trim()));
  check(
    JSON.stringify(finishedCols.slice(0, 6)) ===
      JSON.stringify(["Run", "Kind", "Outcome", "Took", "Finished", "Actions"]),
    `Finished recently columns in the sheet's order: ${JSON.stringify(finishedCols.slice(0, 6))}`,
  );
  const needsBody = (await tables.nth(0).locator("tbody").innerText()) ?? "";
  check(
    needsBody.includes("Waiting to approve"),
    "the awaiting-approval run is drawn with its pill in Needs you",
  );
  const finishedBody = (await tables.nth(1).locator("tbody").innerText()) ?? "";
  check(finishedBody.includes("Done"), "a finished run draws its outcome");
  check(/\d+s|\d+m \d\ds/.test(finishedBody), "and how long it took, in the frame's spelling");

  console.log("── 5 · region 7 — a pagination footer under BOTH tables ────");
  const pagers = await root.locator(".table-pager").count();
  check(pagers === 2, `B14 rule 16: ${pagers} footer(s) — the sheet draws one, the RULE wins`);
  check(/\d+–\d+ of \d+/.test(bodyText), "the footer states a range and a total");

  console.log("── 6 · RBS-001.3 — the run in flight ──────────────────────");
  const banner = root.locator("[data-in-flight]");
  check((await banner.count()) === 1, "the in-flight banner is drawn over a running run");
  check(
    ((await banner.innerText()) ?? "").includes("is running"),
    "and it names the runbook that is running",
  );
  check(
    !/Step \d+ of \d+|seconds left/.test(bodyText),
    "and draws NO progress figure — nothing records one (a bar at an invented percentage is worse than no bar)",
  );
  const stop = banner.locator("button", { hasText: "Stop" });
  check(await stop.isDisabled(), "Stop is disabled — the stop route is the acting half");
  // ⚠ READ FROM COMPUTED STYLE, NEVER FROM A CLASS NAME. B14 rule 21's
  // migration clause means an unlisted file's utility renders as NOTHING while
  // the class sits in the DOM and every `toContain` passes.
  const stopColour = await stop.evaluate((el) => {
    const s = getComputedStyle(el);
    return { color: s.color, border: s.borderTopColor };
  });
  const isRed = (value) => {
    const [r, g, b] = (value.match(/\d+/g) ?? [0, 0, 0]).map(Number);
    return r > 120 && r > g * 1.6 && r > b * 1.6;
  };
  check(
    isRed(stopColour.color) || isRed(stopColour.border),
    `Stop is the DANGER tier, read from computed style: ${JSON.stringify(stopColour)}`,
  );
  const watch = banner.locator('a:has-text("Watch")');
  check((await watch.count()) === 1, "Watch → is a real link");
  await watch.click();
  await page.waitForURL(/\/runbooks\/[^/]+\/runs\/[^/]+$/, { timeout: 30000 });
  // ⚠ **ASSERTED BY URL AND BY CONTENT, BECAUSE `RBS-006` STAMPS NO
  // `data-screen` — `DEF-RBS-4332`, FILED BY THIS WALKTHROUGH.** Every other
  // screen in this product carries its id on its root and `RunbookSetup.tsx`
  // calls that "the convention every screen follows"; `RunResult.tsx` returns a
  // bare fragment, so there is no element to wait for and the first draft of
  // this check timed out against a screen that had rendered perfectly.
  //
  // The substitute is stated rather than made quietly: the address resolved,
  // the not-built-yet marker is absent, and the RUNBOOK'S OWN NAME is on the
  // page — which together say a real run opened. It is weaker than an id and
  // it says so; a check that silently weakens itself is worse than one that
  // fails.
  await page.waitForSelector("h1", { timeout: 30000 });
  const landedText = (await page.locator("body").innerText()) ?? "";
  check(
    (await page.locator('[data-not-built-yet="true"]').count()) === 0,
    `Watch → lands on a real screen rather than the catch-all: ${page.url()}`,
  );
  check(
    landedText.includes("Can we bill?"),
    "and the run that opened is the one the banner named",
  );
  await page.screenshot({ path: join(OUT, "rbs-001-watch-landed.png"), fullPage: true });

  console.log("── 7 · B14 rules 31 and 32 — what a clerk reads ───────────");
  for (const pattern of FORBIDDEN_IN_CLERK_COPY) {
    const hit = bodyText.match(pattern);
    check(hit === null, `no ${pattern} in the clerk-facing text${hit ? ` — found ${hit[0]}` : ""}`);
  }

  console.log("── 8 · the page does not scroll sideways at 1440 ──────────");
  await page.goBack();
  await page.waitForSelector('[data-screen="RBS-001"]', { timeout: 30000 });
  const overflow = await page.evaluate(SIDEWAYS);
  check(overflow === 0, `horizontal overflow at 1440: ${overflow}px`);

  writeFileSync(join(OUT, "wire.json"), JSON.stringify(wire, null, 2));
  await browser.close();

  console.log("");
  if (failures.length > 0) {
    console.error(`⛔ ${failures.length} check(s) failed:`);
    for (const f of failures) console.error(`   · ${f}`);
    process.exit(1);
  }
  console.log(`✓ every check passed. Screenshots and the captured wire are in ${OUT}`);
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
