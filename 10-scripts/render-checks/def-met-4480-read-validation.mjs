/**
 * RENDERED-OUTPUT CHECK — Settings → Configure → Reference data → Read
 * validation & estimation, in a real browser.
 *
 * ⚠ **WHY THIS FILE EXISTS.** Hard-won law 6: no gate in this repository looks
 * at rendered output, so the Product Owner is the detector. Both defects it
 * covers were found that way and could not have been found any other way:
 *
 *   · `DEF-MET-4480` — the page drew its intro, its integrity panel and its
 *     seven chips, and then NOTHING. Every per-service section was missing and
 *     the page read as finished. **REPRODUCED 2026-09-07** by switching the
 *     tenant's services off: `GET /settings/read-validation` answers 200 with
 *     `services: []`, the screen maps an empty array, and the silence is the
 *     bug. Nothing about it is visible to `tsc`, to a unit test, or to any
 *     gate — every element that IS drawn is drawn correctly.
 *   · `DEF-MET-4479` — the two columns of inputs sat at different heights,
 *     because the left field carried a help sentence and the right did not.
 *     **MEASURED 2026-09-07 before the fix**, at 1440px:
 *     `rv-electric-days_hard_min` at y=1450 against `rv-electric-days_hard_max`
 *     at y=1398 — 52px apart, in one row. Every DOM assertion about either
 *     field passed. They only disagree on screen, which is why step 2 below
 *     reads GEOMETRY and not markup.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false
 *   (cd 06-backend && python3.12 manage.py migrate --no-input && \
 *      python3.12 manage.py seed_demo)
 *   (cd 06-backend && python3.12 manage.py runserver 127.0.0.1:8000 --noreload &)
 *   (cd 07-frontend && ./node_modules/.bin/vite build && \
 *      PORT=8080 API_PROXY_TARGET=http://127.0.0.1:8000 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:8080 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/def-met-4480-read-validation.mjs
 *
 * ⚠ **THE TENANT MUST SELL SOME SERVICES IT METERS AND SOME IT DOES NOT** —
 * that is the whole shape of this screen. `seed_demo`'s brazosbend meters
 * electric and water; enable sewer, trash and storm water on it to get the
 * Product Owner's own page:
 *   TenantService.objects.filter(service__code__in=[...]).update(enabled=True)
 *
 * ── WHAT IT ASSERTS ───────────────────────────────────────────────────────
 *   1  **EVERY SERVICE THE TENANT SELLS IS ON THE PAGE**, read from the
 *      server's own answer rather than from a list written here — as a
 *      threshold section if it is metered, as a named entry on the shared
 *      "no meters" line if it is not. This is the check that would have caught
 *      the reported page.
 *   2  **TWO INPUTS IN A ROW SHARE A TOP EDGE**, to the pixel, measured in a
 *      real layout engine over every pair in the grid.
 *   3  **THE PAGE NEVER ENDS IN SILENCE.** With `services: []` — the state
 *      that reproduced the defect — a stated absence is drawn.
 *      ⚠ This one step INTERCEPTS the response rather than switching the
 *      tenant's services off through the database, because the thing under
 *      test is what the SCREEN does with an empty list. The empty list itself
 *      was reproduced against real data; see the header above.
 *   4  **NO INTERNAL CODE REACHES A CLERK** (B14 rules 31 and 32): no rule id,
 *      no defect id, no bare snake_case rule key, no database id.
 *   5  **THE ESTIMATION METHOD IS A CHOICE OF SEVEN**, the two with nothing to
 *      read are present and DISABLED, and the stored default is unchanged.
 *   6  **A PER-SERVICE SAVE DOES NOT LOSE ANOTHER PANEL'S EDIT** — type into
 *      Electric, save Water, and Electric still holds what was typed.
 *   7  **NO SIDEWAYS SCROLL AT 1440.**
 *   8  **A CHOSEN ESTIMATION METHOD ACTUALLY SAVES** — picked, saved, reloaded,
 *      read back from the server, and PUT BACK. Step 5 can only see that the
 *      dropdown has seven options; it cannot tell a live control from a dead
 *      one, which is hard-won law 2's whole subject.
 */

import { execFileSync } from "node:child_process";
import { mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const require = createRequire(join(process.cwd(), "07-frontend", "package.json"));
const { chromium } = require("playwright-core");

function resolveChromium() {
  const wanted = chromium.executablePath();
  try {
    execFileSync(wanted, ["--version"], { stdio: "ignore" });
    return wanted;
  } catch {
    const root = process.env.PLAYWRIGHT_BROWSERS_PATH ?? "/opt/pw-browsers";
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const candidate of [join(root, dir, "chrome-linux", "chrome"), join(root, dir)]) {
        try {
          execFileSync(candidate, ["--version"], { stdio: "ignore" });
          return candidate;
        } catch {
          // keep looking
        }
      }
    }
    return wanted;
  }
}

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:8080";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SMOKE_OUT ?? "/tmp/def-met-4480";
const VIEWPORT = { width: 1440, height: 1200 };
const PAGE_URL = `${BASE}/${TENANT}/settings/reference-data?list=read_validation`;

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

/** Anything a clerk must never be shown (B14 rules 31 and 32). */
const FORBIDDEN_IN_CLERK_COPY = [
  /\bBR-[A-Z]{3}-\d{3,5}\b/,
  /\bOQ-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /\bDEF-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /\bUS-[A-Z]{3}-\d{3,5}\b/,
  /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
  // a bare rule key rendered instead of its name — DEF-MET-4489's shape
  /(?:^|\s)[a-z]+_[a-z_]+(?:\s|$)/m,
];

async function signIn(page) {
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  page.on("pageerror", (e) => check(false, `uncaught page error: ${e.message}`));

  // The SERVER's own answers, captured rather than assumed. Step 1 compares
  // the page against what the server said this tenant sells — a list written
  // in this file would pass on a page that had quietly dropped a section.
  let served = null;
  page.on("response", async (response) => {
    if (!response.url().includes("/settings/read-validation")) return;
    if (response.request().method() !== "GET") return;
    try {
      served = await response.json();
    } catch {
      // a non-JSON body is a different failure and step 1 will report it
    }
  });

  await signIn(page);

  console.log("\n1 · every service the tenant sells is on the page");
  await page.goto(PAGE_URL, { waitUntil: "networkidle" });
  await page.waitForSelector("h1", { timeout: 20000 });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: join(OUT, "01-read-validation.png"), fullPage: true });

  check(served !== null && Array.isArray(served.services), "the server answered with a service list");
  const sold = (served?.services ?? []).map((entry) => entry.service);
  check(sold.length > 0, `the tenant sells ${sold.length} service(s)`);
  for (const code of sold) {
    const listed = await page.locator(`[data-service-listed="${code}"]`).count();
    check(listed > 0, `${code} has a section or a named entry on the page`);
  }

  console.log("\n2 · two inputs in a row share a top edge");
  const rows = await page.evaluate(() => {
    const grids = [...document.querySelectorAll("div.grid")];
    const out = [];
    for (const grid of grids) {
      const inputs = [...grid.querySelectorAll(".field input, .field select")];
      if (inputs.length < 2) continue;
      const byLeft = new Map();
      for (const el of inputs) {
        const r = el.getBoundingClientRect();
        byLeft.set(el.id, { top: Math.round(r.top), left: Math.round(r.left) });
      }
      const entries = [...byLeft.entries()];
      // pair them the way the grid lays them out: two columns, source order
      for (let i = 0; i + 1 < entries.length; i += 2) {
        const [aId, a] = entries[i];
        const [bId, b] = entries[i + 1];
        if (a.left === b.left) continue; // wrapped to one column; nothing to pair
        out.push({ a: aId, b: bId, aTop: a.top, bTop: b.top });
      }
    }
    return out;
  });
  check(rows.length > 0, `found ${rows.length} paired row(s) to measure`);
  for (const row of rows) {
    check(
      row.aTop === row.bTop,
      `${row.a} (y=${row.aTop}) and ${row.b} (y=${row.bTop}) share a top edge`,
    );
  }

  console.log("\n4 · no internal code reaches a clerk");
  await page.goto(PAGE_URL, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  const bodyText = await page.evaluate(() => {
    const main = document.querySelector("main") ?? document.body;
    return main.innerText;
  });
  for (const pattern of FORBIDDEN_IN_CLERK_COPY) {
    const hit = bodyText.match(pattern);
    check(hit === null, `no clerk-facing ${pattern} (found: ${hit?.[0]?.trim() ?? "none"})`);
  }

  console.log("\n5 · the estimation method is a choice of seven");
  const method = await page.evaluate(() => {
    const el = document.getElementById("rv-est_method");
    if (el === null) return null;
    return {
      tag: el.tagName,
      value: el.value,
      options: [...el.options].map((o) => ({ value: o.value, disabled: o.disabled })),
    };
  });
  check(method?.tag === "SELECT", "the method is a dropdown, not a fixed box");
  check(method?.options.length === 7, `seven methods offered (found ${method?.options.length})`);
  check(method?.value === "trailing_3_daily_avg", `the stored default is unchanged (${method?.value})`);
  const held = (method?.options ?? []).filter((o) => o.disabled).map((o) => o.value);
  check(
    held.length === 2 && held.includes("route_peer_average") && held.includes("plan_average"),
    `the two methods with nothing to read are offered and not selectable (${held.join(", ")})`,
  );

  console.log("\n6 · a per-service save does not lose another panel's edit");
  // Electric lands open. Type into it, open Water, save Water, come back.
  const electricHigh = page.locator("#rv-electric-high_pct");
  if ((await electricHigh.count()) > 0) {
    await electricHigh.fill("222");
    await page.locator('button:has-text("Water")').first().click();
    await page.waitForTimeout(400);
    const waterSave = page.locator('button:has-text("Save Water thresholds")');
    if ((await waterSave.count()) > 0) {
      await page.locator("#rv-water-low_pct").fill("26");
      await waterSave.first().click();
      await page.waitForTimeout(2000);
    }
    check(
      (await electricHigh.inputValue()) === "222",
      "the Electric edit survives a Water save",
    );
    check(
      (await page.locator('[data-service-listed="electric"]').count()) > 0,
      "Electric is still on the page after the save",
    );
  } else {
    check(false, "the Electric panel did not open — cannot test the save");
  }

  console.log("\n7 · no sideways scroll at 1440");
  const overflow = await page.evaluate(
    () =>
      Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth),
  );
  check(overflow === 0, `no horizontal overflow (${overflow}px)`);

  await page.screenshot({ path: join(OUT, "03-final.png"), fullPage: true });

  console.log("\n8 · a chosen estimation method actually SAVES");
  // ⚠ **THIS STEP EXISTS BECAUSE THE CHECK ABOVE IT IS NOT ENOUGH.** Step 5
  // asks whether the dropdown has seven options and whether two are held. It
  // cannot tell a live control from a dead one — hard-won law 2 — and on
  // 2026-09-07 the first run of this walkthrough met a 422 on exactly this
  // path. (That one was a server running pre-change code with `--noreload`,
  // not a defect; the point is that NOTHING here would have told the
  // difference between that and a dropdown that never saves.)
  let saveStatus = null;
  const watch = async (response) => {
    if (response.url().includes("/settings/read-validation") && response.request().method() === "PUT") {
      saveStatus = response.status();
    }
  };
  page.on("response", watch);
  const before = await page.locator("#rv-est_method").inputValue();
  await page.selectOption("#rv-est_method", "trailing_12_daily_avg");
  await page.locator('button:has-text("Save estimation settings")').first().click();
  await page.waitForTimeout(2500);
  check(saveStatus === 200, `the save was accepted (HTTP ${saveStatus})`);
  await page.goto(PAGE_URL, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  check(
    (await page.locator("#rv-est_method").inputValue()) === "trailing_12_daily_avg",
    "…and it is still chosen after a reload, read back from the server",
  );
  const guidance = await page.locator("[data-est-method-when]").innerText();
  check(guidance.trim().length > 0, `…and the line under it follows the choice ("${guidance.slice(0, 48)}…")`);
  // PUT THE TENANT BACK. A walkthrough that leaves a utility on a different
  // estimation method has changed what its customers are billed.
  await page.selectOption("#rv-est_method", before);
  await page.locator('button:has-text("Save estimation settings")').first().click();
  await page.waitForTimeout(2500);
  await page.goto(PAGE_URL, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  check(
    (await page.locator("#rv-est_method").inputValue()) === before,
    `the tenant is back on the method it started with (${before})`,
  );
  page.off("response", watch);

  console.log("\n3 · the page never ends in silence");
  // ⚠ LAST, AND ON ITS OWN PAGE. An earlier draft ran this in the middle and
  // fulfilled the request with `route.fetch()`, which re-issues it WITHOUT the
  // session: the server answered 401, the screen drew its permission-denied
  // frame, and every later step failed against a page that was not the page
  // under test. The body is built from the payload the server already gave us
  // in step 1, so nothing is re-fetched and nothing is invented.
  const empty = await context.newPage();
  empty.on("pageerror", (e) => check(false, `uncaught page error (empty case): ${e.message}`));
  await empty.route("**/settings/read-validation", async (route) => {
    if (route.request().method() !== "GET") return route.continue();
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ...served, services: [] }),
    });
  });
  await empty.goto(PAGE_URL, { waitUntil: "networkidle" });
  await empty.waitForTimeout(1500);
  await empty.screenshot({ path: join(OUT, "02-no-services.png"), fullPage: true });
  const emptyText = await empty.evaluate(() => document.body.innerText);
  check(
    (await empty.locator("[data-no-services]").count()) > 0,
    "with no service switched on, the page SAYS so rather than stopping after the chips",
  );
  check(
    emptyText.includes("Integrity checks"),
    "…and it is the real screen we are looking at, not an error frame",
  );

  await browser.close();

  console.log(`\nscreenshots: ${OUT}`);
  if (failures.length > 0) {
    console.log(`\n⛔ ${failures.length} failure(s):`);
    for (const f of failures) console.log(`   · ${f}`);
    process.exit(1);
  }
  console.log("\n✓ all checks passed");
})();
