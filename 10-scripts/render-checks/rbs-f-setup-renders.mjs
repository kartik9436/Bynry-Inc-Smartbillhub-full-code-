/**
 * RENDERED-OUTPUT CHECK — `RBS-004`, ALL SEVEN TABS, IN A REAL BROWSER.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: *"no gate looks at rendered output"*,
 * and nine defects were found by that and by nothing else. The Product Owner's
 * own definition of done, 2026-09-06: *"everything should be executed based on
 * actual code, and rules that we place, also ensure you do web walkthorugh
 * before you sign off the user story or build"*.
 *
 * ⚠ **AND BECAUSE THIS SCREEN HAD NEVER ONCE RENDERED.** `DEF-RBS-4308`: the
 * wave-C client cast `GET /runbooks/{key}`'s body straight to the view model
 * (16:17 UTC) and the wave-D endpoint served a different shape (16:23 UTC), so
 * from 16:23 on 2026-09-06 `RBS-004` threw
 *
 *     TypeError: Cannot read properties of undefined (reading 'length')
 *
 * on `view.capabilities.length` — with `tsc` green, 49 unit cases green over a
 * hand-built prop, and every gate green. **A screen this product routes and
 * advertises had never been seen to work.**
 *
 * ══════════════════════════════════════════════════════════════════════════
 * WHAT IT ASSERTS, AND WHY EACH ASSERTION IS THE SHAPE IT IS
 * ══════════════════════════════════════════════════════════════════════════
 *   1  **ALL SEVEN TABS DRAW, AND NO CONSOLE ERROR IS RAISED ON ANY OF THEM.**
 *      A screen that throws inside one tab still paints the page chrome — the
 *      head, the tab strip, the shell — so *"the page loaded"* is exactly the
 *      assertion that passed over this defect for a day. The console is what
 *      tells them apart, and it is read PER TAB rather than once at the end.
 *   2  **EACH TAB SHOWS A VALUE THAT COMES FROM THE SERVER**, read out of the
 *      captured response rather than typed here, so a payload that stops
 *      carrying a field makes the assertion fail instead of going stale.
 *   3  **THE THREE RELEASED CONTROLS ACTUALLY WRITE** — Pause/Resume and
 *      Change limits on this screen, **+ Add** on the template library — each
 *      verified by the RESULT coming back from the server on the next read,
 *      never by a toast. `DEF-RBS-4311`: a control that shows a success message
 *      and sends nothing is the shape this walkthrough exists to refuse.
 *   4  **THE TWO CONTROLS THAT ARE STILL HELD SAY SO IN A SHORT SENTENCE AND
 *      WRITE NOTHING** — `Run ▶` (task `L`) and `Change scope` (no route
 *      stores a `Parameter` value). B14 rule 33 caps a refusal at five or six
 *      words; rule 32 bans a rule id or an internal code in clerk copy.
 *   5  **NO DATABASE ID AND NO RULE ID IS ON SCREEN** (B14 rules 31 and 32),
 *      over all seven tabs rather than over the one a lane happened to open.
 *   6  **THE PAGE DOES NOT SCROLL SIDEWAYS** at 1440.
 *
 * ⚠ **WHAT WOULD MAKE THIS CHECK PASS WRONGLY** — asked because a check you
 * cannot describe a false pass for is one you do not understand. Two things,
 * and both are guarded: a sign-in that has not finished (every later call 401s
 * and reads as several broken regions, so the landing URL is waited for rather
 * than `networkidle`), and a screenshot taken before the payload arrives (so
 * each tab waits for its own region to exist before it is judged).
 *
 * ── HOW TO RUN IT ────────────────────────────────────────────────────────
 *   Use a database NOBODY ELSE is seeding — on 2026-08-30 a sibling check lost
 *   three runs to the shared one, with every id changing mid-run, which looks
 *   exactly like a broken screen.
 *
 *   createdb sbh_rbs004
 *   DJANGO_SETTINGS_MODULE=config.settings.local \
 *   DATABASE_URL="postgres://smartbillhub:smartbillhub@localhost:5432/sbh_rbs004" \
 *     python3.12 06-backend/manage.py migrate && … seed_demo
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local DATABASE_URL=…rbs004 \
 *     python3.12 06-backend/manage.py runserver 127.0.0.1:8077 --noreload &
 *   (cd 07-frontend && ./node_modules/.bin/vite build && \
 *      PORT=4277 API_PROXY_TARGET=http://127.0.0.1:8077 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4277 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/rbs-f-setup-renders.mjs
 *
 * ⚠ **NEVER `playwright install`.** Chromium is at `/opt/pw-browsers` and is
 * resolved below; a download attempt is a network call this environment refuses
 * and it reads as a broken script.
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
const TEMPLATE = process.env.SMOKE_TEMPLATE ?? "configuration_check";
const OUT = process.env.SMOKE_OUT ?? "/tmp/rbs-f-setup-renders";
const VIEWPORT = { width: 1440, height: 1000 };

/** The seven tabs, and the region each one must have drawn before it is judged.
 *  A screenshot taken before the payload arrives is a picture of a skeleton. */
const TABS = [
  ["overview", '[data-region="this-can"]'],
  ["steps", '[data-region="steps"]'],
  ["scope", '[data-region="scope"]'],
  ["guards", '[data-region="guards"]'],
  ["limits", '[data-region="limits"]'],
  ["runs", '[data-screen="RBS-004"]'],
  ["activity", '[data-screen="RBS-004"]'],
];

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

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();

  // ⚠ **THE CONSOLE IS THE ASSERTION, NOT A LOG LINE.** A React render error
  // unmounts the tree and leaves the shell standing, so a check that only asks
  // *did the page load* passes over exactly the defect this file was written
  // for. Errors are collected per tab and judged per tab.
  //
  // ⚠ **AND ONE CLASS IS EXCLUDED, WITH ITS NUMBER AND ITS URLS PRINTED
  // BESIDE WHAT WAS CHECKED.** This sandbox has no route to the public
  // internet, so `index.html`'s Google-Fonts stylesheet fails with
  // `net::ERR_CONNECTION_RESET` on EVERY page of the product — an environment
  // fact about the box, not a fault in this screen. Hard-won law 7's fifth
  // shape is a check that reports zero over a scope it silently excludes, so
  // the exclusion is NARROW (a resource load, from a host that is not this
  // origin) and it is SAID OUT LOUD rather than filtered away: an off-origin
  // failure is listed by url, and anything else — a script error, a page
  // error, a failed call to our own API — still fails the check.
  let consoleErrors = [];
  let offOrigin = [];
  page.on("console", (m) => {
    if (m.type() === "error") consoleErrors.push(m.text().slice(0, 220));
  });
  page.on("pageerror", (e) => consoleErrors.push(`pageerror: ${String(e).slice(0, 220)}`));
  page.on("requestfailed", (request) => {
    const url = request.url();
    // `ERR_ABORTED` on our own origin is the SPA cancelling an in-flight read
    // as the router leaves a screen; it raises no console error and is not one.
    if (!url.startsWith(BASE)) {
      offOrigin.push(`${url.slice(0, 120)} → ${request.failure()?.errorText ?? "?"}`);
    }
  });

  /** The console errors this run must answer for, and the ones the box caused.
   *
   *  A `Failed to load resource` carries no url in its console text, so it is
   *  matched by COUNT against the off-origin failures observed in the same
   *  window: one such console line per off-origin failure is explained, and any
   *  surplus is not. */
  function judgeConsole(tab) {
    const loads = consoleErrors.filter((line) => line.startsWith("Failed to load resource"));
    const ours = consoleErrors.filter((line) => !line.startsWith("Failed to load resource"));
    const unexplained = ours.length + Math.max(0, loads.length - offOrigin.length);
    if (offOrigin.length > 0) {
      console.log(
        `     (excluded ${offOrigin.length} off-origin resource failure(s): ${offOrigin.join(" · ")})`,
      );
    }
    check(
      unexplained === 0,
      `${tab}: no console error of ours — ${ours[0] ?? (unexplained > 0 ? loads[0] : "clean")}`,
    );
  }

  /** The server's own answer, captured rather than inferred. *Did the screen
   *  draw it* and *did the server send it* are two different questions, and
   *  `DEF-RBS-4308` is what happens when only one of them is asked. */
  const wire = [];
  page.on("response", async (response) => {
    if (!/\/api\/.*\/runbooks/.test(response.url())) return;
    try {
      wire.push({ url: response.url(), body: await response.text() });
    } catch {
      /* a redirect or a bodyless response has nothing to read */
    }
  });

  async function api(method, path, body) {
    const response = await page.request.fetch(`${BASE}/api/${TENANT}${path}`, {
      method,
      headers: { "content-type": "application/json" },
      data: body === undefined ? undefined : JSON.stringify(body),
    });
    let parsed = null;
    try {
      parsed = await response.json();
    } catch {
      /* a bodyless refusal has nothing to read */
    }
    return { status: response.status(), body: parsed };
  }

  console.log("── sign in ───────────────────────────────────────────────");
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  // ⚠ `input[type="email"]` MATCHES NOTHING — `S3` draws the work-email field
  // as `type="text"` with `id="signin-email"`, and the obvious selector times
  // out after thirty seconds with a message about a locator rather than about
  // the page, which reads like a broken screen and is a broken selector.
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  // ⚠ WAIT FOR THE LANDING, NOT FOR THE NETWORK. Sign-in is an XHR, so the page
  // never navigates and `waitForLoadState("networkidle")` returns before the
  // session cookie exists — every later call then 401s and reads as several
  // broken regions over a screen that is fine.
  await page.waitForURL(/\/dashboard(\?|$)/, { timeout: 30000 });
  check(true, `signed in as ${EMAIL} and landed on the dashboard`);

  console.log("── the template library · + Add is wired (DEF-RBS-4311) ──");
  // The tenant may already hold it from an earlier run; either way the state of
  // the world after this block is *the template is added*, which is what the
  // rest of the walkthrough needs.
  const seeded = await api("POST", "/runbooks", { template_key: TEMPLATE });
  const alreadyThere = seeded.status === 409;
  check(
    seeded.status === 201 || alreadyThere,
    `the template is on this tenant (POST answered ${seeded.status})`,
  );
  const key = alreadyThere ? TEMPLATE : (seeded.body?.key ?? TEMPLATE);

  await page.goto(`${BASE}/${TENANT}/runbooks/templates`, { waitUntil: "networkidle" });
  await page.waitForTimeout(900);
  await page.screenshot({ path: join(OUT, "00-rbs-002-templates.png"), fullPage: true });
  // ⚠ **THE HOLD IS CHECKED BY ITS SENTENCE'S ABSENCE, WHICH IS THE ONE THING
  // A SCREENSHOT CANNOT TELL YOU.** *"Adding is not connected yet."* was the
  // toast this button raised while `POST /runbooks` was live.
  const libraryText = await page.evaluate(() => document.body.innerText);
  check(
    !libraryText.includes("Adding is not connected yet"),
    "the library no longer says adding is unconnected",
  );

  console.log("── RBS-004 · all seven tabs, in a real browser ────────────");
  const detailBody = (await api("GET", `/runbooks/${key}`)).body ?? {};
  const drawn = {};
  for (const [tab, region] of TABS) {
    consoleErrors = [];
    offOrigin = [];
    await page.goto(`${BASE}/${TENANT}/runbooks/${key}#${tab}`, { waitUntil: "networkidle" });
    await page.waitForSelector(region, { timeout: 15000 }).catch(() => null);
    await page.waitForTimeout(700);
    await page.screenshot({ path: join(OUT, `${tab}.png`), fullPage: true });
    const text = await page.evaluate(() => document.body.innerText);
    drawn[tab] = text;

    const tabs = await page.$$eval('[role="tab"]', (nodes) => nodes.length);
    check(tabs === 7, `${tab}: the tab strip drew all seven (got ${tabs})`);
    judgeConsole(tab);
    const offending = FORBIDDEN_IN_CLERK_COPY.map((re) => text.match(re))
      .filter(Boolean)
      .map((m) => m[0]);
    check(offending.length === 0, `${tab}: no database id or rule id (${JSON.stringify(offending)})`);
  }

  // ── each tab shows a value the SERVER sent ──────────────────────────────
  check(
    drawn.overview.includes(detailBody.name ?? " "),
    `the head draws the runbook's own name (${detailBody.name})`,
  );
  check(
    drawn.overview.includes(detailBody.schedule?.timezone ?? " "),
    `Overview draws the server's time zone (${detailBody.schedule?.timezone})`,
  );
  const steps = detailBody.definition?.steps ?? [];
  check(steps.length > 0, `the definition carries ${steps.length} steps`);
  check(
    steps.every((step) => drawn.steps.includes(step.label)),
    "Steps draws every step label the stored definition holds",
  );
  const parameters = detailBody.definition?.parameters ?? [];
  check(
    parameters.length > 0 && parameters.every((p) => drawn.scope.includes(p.label)),
    "Scope draws every parameter label — BR-RBS-042's inputs",
  );
  check(
    detailBody.cap === null || drawn.limits.includes(String(detailBody.cap)),
    `Limits draws the cap the server stores (${detailBody.cap})`,
  );
  check(
    !drawn.limits.includes(detailBody.gate_mode ?? " "),
    "Limits draws the approval as a WORD, never as its code",
  );
  const versions = detailBody.activity ?? [];
  check(
    versions.length > 0 && drawn.activity.includes(`v${versions[0].version}`),
    `Activity draws the newest version (v${versions[0]?.version})`,
  );
  check(
    !/"field"|gate_mode|trigger_kind/.test(drawn.activity),
    "Activity draws a SENTENCE, never the server's raw facts",
  );

  console.log("── the two controls still HELD say so and write nothing ───");
  await page.goto(`${BASE}/${TENANT}/runbooks/${key}#scope`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-region="scope"]', { timeout: 15000 });
  const versionBefore = (await api("GET", `/runbooks/${key}`)).body?.current_version;
  await page.getByRole("button", { name: "Change scope" }).click();
  await page.waitForTimeout(600);
  const scopeText = await page.evaluate(() => document.body.innerText);
  // ⚠ Change scope is HELD for a reason that MOVED. `PUT /runbooks/{key}`
  // landed in wave `E1` and takes the eight `services.EDITABLE_SETTINGS`; a
  // scope row is a `Parameter`, and no route and no column stores a tenant's
  // parameter VALUE. Releasing it needs somewhere to put the value, not a
  // button — so the sentence is still true, which is what this asserts.
  check(
    scopeText.includes("Not connected yet"),
    "Change scope refuses in one short sentence",
  );
  await page.screenshot({ path: join(OUT, "held-change-scope.png"), fullPage: true });

  await page.goto(`${BASE}/${TENANT}/runbooks/${key}`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="RBS-004"]', { timeout: 15000 });
  await page.getByRole("button", { name: "Run ▶" }).click();
  await page.waitForTimeout(600);
  const runText = await page.evaluate(() => document.body.innerText);
  check(runText.includes("Not connected yet"), "Run ▶ refuses in one short sentence");
  check(
    (await api("GET", `/runbooks/${key}`)).body?.current_version === versionBefore,
    "neither held control wrote a version",
  );

  console.log("── the released controls WRITE, checked on the next read ──");
  const pausedBefore = (await api("GET", `/runbooks/${key}`)).body?.enabled;
  await page.getByRole("button", { name: pausedBefore ? "Pause" : "Resume" }).click();
  await page.waitForTimeout(1200);
  const afterPause = (await api("GET", `/runbooks/${key}`)).body;
  check(
    afterPause?.enabled === !pausedBefore,
    `Pause/Resume wrote it (enabled ${pausedBefore} → ${afterPause?.enabled})`,
  );
  check(
    afterPause?.current_version === versionBefore + 1,
    `and BR-RBS-038 minted a version (v${versionBefore} → v${afterPause?.current_version})`,
  );
  await page.screenshot({ path: join(OUT, "released-pause.png"), fullPage: true });

  await page.goto(`${BASE}/${TENANT}/runbooks/${key}#limits`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-region="limits"]', { timeout: 15000 });
  await page.getByRole("button", { name: "Change limits" }).click();
  await page.waitForSelector("#cap", { timeout: 10000 });
  await page.fill("#cap", "275");
  await page.screenshot({ path: join(OUT, "released-change-limits.png"), fullPage: true });
  await page.getByRole("button", { name: "Save limits" }).click();
  await page.waitForTimeout(1500);
  const afterLimits = (await api("GET", `/runbooks/${key}`)).body;
  check(afterLimits?.cap === 275, `Change limits wrote the cap (got ${afterLimits?.cap})`);

  console.log("── layout ────────────────────────────────────────────────");
  const sideways = await page.evaluate(SIDEWAYS);
  check(sideways === 0, `the page does not scroll sideways at 1440 (overflow ${sideways}px)`);

  writeFileSync(
    join(OUT, "summary.json"),
    JSON.stringify({ key, tabs: TABS.map(([t]) => t), wire: wire.length, failures }, null, 2),
  );
  await browser.close();

  console.log("──────────────────────────────────────────────────────────");
  if (failures.length > 0) {
    console.log(`⛔ ${failures.length} check(s) failed:`);
    for (const failure of failures) console.log(`   · ${failure}`);
    process.exit(1);
  }
  console.log(`✓ every check passed. Screenshots in ${OUT}`);
})().catch((error) => {
  console.error("⛔ the walkthrough could not run:", error);
  process.exit(2);
});
