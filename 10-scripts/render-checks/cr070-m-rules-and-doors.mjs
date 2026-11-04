/**
 * RENDERED-OUTPUT CHECK — CR-070 wave M's demo script, clicked.
 *
 * `US-WRK-037` (rules that raise work orders overnight) and `US-WRK-038` (the
 * Assets door: one form, four ways in). Journeys `J63`. Screens `Work-026`,
 * `Work-028`, `Work-007`, and the asset detail's Maintenance history.
 *
 * ⚠ **THE MOVE-OUT LEG IS NOT HERE.** It moved to wave `P` on 2026-09-04
 * (`CR-070 §W.10`) and its walk is `P7`'s. The plan's own text for that step
 * named two different wizard steps at once — *step 4 → tick the final read*,
 * when the final read is step 2 — and `DEF-WRK-3725` records it.
 *
 * ⚠ **WHY A CLICKED SCRIPT AND NOT MORE UNIT TESTS.** No check in this
 * repository reads rendered output (CLAUDE.md hard-won law 6), and this wave's
 * two most expensive failure modes are both invisible to the DOM:
 *
 *   · **A TAILWIND UTILITY IN A FILE THAT IS NOT ON `route-b-migrated.txt`**
 *     renders as NOTHING AT ALL while `tsc`, eslint and every
 *     `toContain("flex")` assertion pass, because the class IS in the DOM. The
 *     Work map lost its entire background to exactly this on 2026-09-05. Only
 *     computed style can see it, so step 1 reads one.
 *   · **A CONTROL THAT LOOKS LIVE AND REFUSES** — hard-won law 2's mirror
 *     clause. `G13` asks whether a prop is passed; nothing asks whether a
 *     refusal is still TRUE. On 2026-09-05 the customer portal's front page had
 *     two working doors out of eight (`DEF-CWP-3925`). Steps 6 and 7 press the
 *     controls this wave released and assert where the browser actually goes.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   su postgres -c "psql -c 'create database sbh_wavem owner smartbillhub'"
 *   export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
 *     DATABASE_URL="postgres://smartbillhub:<pw>@127.0.0.1:5432/sbh_wavem"
 *   (cd 06-backend && python manage.py migrate --no-input && python manage.py seed_demo \
 *      && python manage.py load_sample_data --tenant brazosbend)
 *   (cd 06-backend && ALLOWED_HOSTS='*' python manage.py runserver 127.0.0.1:8130 --noreload &)
 *   (cd 07-frontend && npx vite build && \
 *      PORT=4330 API_PROXY_TARGET=http://127.0.0.1:8130 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4330 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr070-m-rules-and-doors.mjs
 *
 * ── ⚠ RUN ON 2026-09-05, AND WHAT IT FOUND ──────────────────────────────
 * The fixture `DEF-WRK-4085` asked for now exists (`apps/work/sample_data.py`
 * seeds the seven rules; `apps/assets/sample_data.seed_sample_aged_meters`
 * seeds `AST-04412`, `AST-04413`, `AST-04414`), so this script was run against
 * a freshly seeded tenant on real PostgreSQL 16. **It found five faults that
 * 14 new sample-data cases, 25 engine cases, `tsc`, eslint and 85 passing
 * gates were all green over** — which is what a walkthrough is for (law 6):
 *
 *   1 **`DEF-WRK-4098` — `Work-026` drew ZERO rules for every tenant.** The
 *     endpoint serves `{count, next, previous, results}`; the page read
 *     `data.rows` / `data.total`. `tsc` cannot see it: the generic on
 *     `client.get<T>()` is an assertion, not a check. FIXED, with a mounting
 *     test that goes red on the old shape.
 *   2 **`DEF-WRK-4096` — four of the five triggers cannot raise at all**, and
 *     the fifth stamps the wrong source, which is why step 2 below reads
 *     *Assets* where it should read *Asset age rule*. `_raise_one` stamps
 *     `source = rule.source_module`; `create_work_order` validates against
 *     `WORK_ORDER_SOURCES`. NOT fixed here — the mapping is a product
 *     statement, and `work.orders.source.asset_age_rule` already exists in all
 *     eleven catalogues waiting for it.
 *   3 **`DEF-WRK-4097` — the leak rule matches 98 of ~98 meters**, so fixing 2
 *     without 3 floods every trial tenant.
 *   4 **This script asked the METERS tab for a control on the INVENTORY tab**
 *     and reported it missing. Fixed above.
 *   5 **This script's own "and it is ENABLED" check passed over a page with no
 *     checkbox**, because `[].every(...)` is true. Fixed above.
 *
 * ⚠ **TWO STEPS STILL CANNOT BE DEMONSTRATED, AND NEITHER IS A PRODUCT BUG.**
 *   · **The Maintenance history (step 6).** `AssetMaintenance` holds ZERO rows
 *     on a seeded tenant, and `asset_door.maintenance_history_index` keys work
 *     orders BY DATE onto existing maintenance rows — so the Work-order column
 *     lights up only where a maintenance row shares the order's date. There is
 *     nothing for `WO-4908` to appear beside. `DEF-WRK-4099`.
 *   · **The retire pre-tick (step 7).** It renders on **step 2** of the retire
 *     wizard (*Replacement*), and only when `measuring && asset.assigned`.
 *     This script loads step 1, and the seeded `AST-04412` is in INVENTORY —
 *     the fixture put it there deliberately, because seating it on
 *     `221 Oak Ave · Unit 3` as the drawing does would put a second live meter
 *     on a service point that already has one and move this tenant's billing.
 *     `DEF-WRK-4099` records the trade-off.
 *
 * ⚠ **BUILD THE BUNDLE.** A stale `dist/` is the most expensive way to read
 * this script's output: every assertion then passes or fails about a build
 * nobody is shipping.
 *
 * ⚠ **THE SWEEP IS RUN FROM THE TERMINAL, NOT FROM A BUTTON.** There is no
 * *run the rules now* control and this wave does not invent one — the sweep is
 * a nightly job. Between steps 2 and 3 the script pauses and asks the operator
 * to run, in another shell:
 *     (cd 06-backend && python manage.py shell -c \
 *       "from core.tenancy import tenant_context; from apps.tenancy.models import Tenant; \
 *        from apps.work import rules; t=Tenant.objects.get(subdomain='brazosbend'); \
 *        ctx=tenant_context(t.id); ctx.__enter__(); print(rules.sweep(None))")
 * Set `SMOKE_SWEEP=auto` to have the script shell out and do it itself.
 *
 * ── WHAT IT ASSERTS (the demo script, step for step) ──────────────────────
 *   1  Work → **Rules** lists SEVEN rules, SIX of them On — and the strip has
 *      eight tabs with Rules between Templates and Performance. Computed style
 *      is read on the page so a missing `route-b-migrated.txt` line cannot hide.
 *   2  The night's sweep runs → THREE *Meter exchange* orders appear on
 *      `Work-007`, each reading **Raised by: Asset age rule**.
 *   3  The next night raises NONE — the same sweep, run twice.
 *   4  The rule is switched **Off** and the sweep raises none at all.
 *   5  Assets → `AST-04412` → *Raise work order* → the template list holds ONLY
 *      templates whose asset types include this one.
 *   6  Raise it → `WO-4908` is in the dispatcher with CONNECTION a dash, and the
 *      asset's Maintenance history reads `WO-4908` where it read a dash.
 *   7  The four pre-ticks are ENABLED and the DOM carries no *Work R5* anywhere;
 *      pressing *Parts in Work →* lands on the parts register.
 *   Screenshots land in `$SMOKE_OUT` beside `Work-026.png` and `Work-028.png`.
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
          // try the next layout
        }
      }
    }
    throw new Error("no chromium found — set PLAYWRIGHT_BROWSERS_PATH");
  }
}

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4330";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr070-m-rules-and-doors";
const ASSET_NO = process.env.SMOKE_ASSET ?? "AST-04412";
const VIEWPORT = { width: 1440, height: 1000 };

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

/**
 * **DID WE ACTUALLY ARRIVE?** — asserted before any other claim about a page.
 *
 * ⚠ **TWO HABITS, BOTH LEARNED EXPENSIVELY ON 2026-09-05.** A screen that never
 * loaded and a screen that loaded empty are indistinguishable to a `$$eval` that
 * returns `[]`, so a zero-result assertion passes just as happily over a page
 * that was never rendered — that is how a check on wave L passed over a page
 * that had never loaded. And `NotBuiltYet` renders a perfectly good `<h1>` at
 * any unrouted address, so a page can look present and be the placeholder.
 *
 * So: name a witness that is on THIS screen and nowhere else, and rule the
 * placeholder out BY ITS OWN MARKER rather than by absence of something.
 */
async function arrived(page, witness, label) {
  const placeholder = await page.$("[data-not-built-yet]");
  check(placeholder === null, `${label}: is a real screen, not "This screen is not built yet"`);
  const text = await page.$eval("body", (el) => el.innerText);
  check(text.includes(witness), `${label}: shows its own witness ${JSON.stringify(witness)}`);
}

/** Run the nightly sweep the way the product runs it: as the job, not a button. */
function runSweep(label) {
  const code =
    "from core.tenancy import tenant_context;" +
    "from apps.tenancy.models import Tenant;" +
    "from apps.work import rules;" +
    `t=Tenant.objects.get(subdomain='${TENANT}');` +
    "ctx=tenant_context(t.id); ctx.__enter__();" +
    "print('SWEEP', rules.sweep(None))";
  const out = execFileSync("python", ["manage.py", "shell", "-c", code], {
    cwd: join(process.cwd(), "06-backend"),
    encoding: "utf-8",
  });
  const line = out.split("\n").find((l) => l.startsWith("SWEEP")) ?? out.trim();
  console.log(`   · ${label}: ${line}`);
  return line;
}

async function signIn(page) {
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });
}

/** Every row of `Work-026`, as a person reads it. */
const READ_RULES = () =>
  Array.from(document.querySelectorAll("tbody tr")).map((tr) => {
    const cells = Array.from(tr.querySelectorAll("td")).map((td) => td.innerText.trim());
    return { cells, enabled: /\bOn\b/.test(cells[6] ?? "") };
  });

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 160)}`);
  });

  console.log(`cr070-m: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);
  await signIn(page);

  // ═══ 1 · Work → Rules: seven rules, six On ═══════════════════════════════
  await page.goto(`${BASE}/${TENANT}/work/rules`, { waitUntil: "networkidle" });
  await page.screenshot({ path: join(OUT, "Work-026.png"), fullPage: true });

  const tabs = await page.$$eval("[data-page-header-tabs] [data-tab]", (els) =>
    els.map((e) => e.getAttribute("data-tab")),
  );
  check(tabs.length === 8, `the Work strip has eight tabs (saw ${tabs.length}: ${tabs.join(", ")})`);
  check(
    tabs.indexOf("rules") === tabs.indexOf("templates") + 1 &&
      tabs.indexOf("rules") === tabs.indexOf("performance") - 1,
    "Rules sits between Templates and Performance, which is the inventory's order",
  );

  const rules = await page.evaluate(READ_RULES);
  check(rules.length === 7, `Rules lists seven rules (saw ${rules.length})`);
  check(
    rules.filter((r) => r.enabled).length === 6,
    `six of them are On (saw ${rules.filter((r) => r.enabled).length})`,
  );

  // ⚠ THE ASSERTION ONLY COMPUTED STYLE CAN MAKE. `RulesPage.tsx` is written in
  // Tailwind utilities and is on `route-b-migrated.txt`; if that line were ever
  // dropped the utilities would emit NOTHING and this page would render as
  // unstyled text with every DOM assertion above still passing.
  const consequence = await page.$eval("[data-consequence='work-rules']", (el) => {
    const s = getComputedStyle(el);
    return { border: s.borderTopWidth, padding: s.paddingLeft, display: s.display };
  });
  check(
    parseFloat(consequence.padding) > 0 && consequence.display !== "inline",
    `the consequence box is really styled (padding ${consequence.padding}, display ${consequence.display}) — a missing route-b-migrated.txt line renders it as nothing`,
  );

  // ⚠ B14 rule 31 — no database id is the visible value of any field.
  const rulesText = await page.$eval("tbody", (el) => el.innerText);
  check(
    !/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}/i.test(rulesText),
    "no uuid is visible in any rule row (B14 rule 31)",
  );

  // ═══ 2 · the night's sweep → three orders, each saying why ═══════════════
  if (process.env.SMOKE_SWEEP === "auto") {
    runSweep("first night");
  } else {
    console.log("\n   ⏸  run the sweep now (see the header), then press Enter");
    await new Promise((resolve) => process.stdin.once("data", resolve));
  }

  await page.goto(`${BASE}/${TENANT}/work/orders`, { waitUntil: "networkidle" });
  await page.screenshot({ path: join(OUT, "Work-007-after-sweep.png"), fullPage: true });
  const raisedBy = await page.$$eval("tbody tr", (rows) =>
    rows.map((r) => r.innerText).filter((t) => /Asset age rule/.test(t)),
  );
  check(raisedBy.length === 3, `three orders read "Asset age rule" (saw ${raisedBy.length})`);
  // ⚠ **`raisedBy.length === 3 &&` IS LOAD-BEARING.** `[].every(...)` is TRUE,
  // so on the 2026-09-05 run this line reported a PASS — *"every one of them
  // is a Meter exchange"* — about an empty list, one line under the ⛔ that
  // said none were found. That is the third vacuous assertion in this file and
  // the reason to state the rule rather than fix them one at a time: **pair
  // every claim about a set with a positive that the set is not empty.**
  check(
    raisedBy.length === 3 && raisedBy.every((t) => /Meter exchange/.test(t)),
    "every one of them is a Meter exchange",
  );

  // ═══ 3 · the next night raises none ══════════════════════════════════════
  if (process.env.SMOKE_SWEEP === "auto") {
    const second = runSweep("second night");
    check(/'raised': 0/.test(second), "the second sweep raises nothing (idempotent per rule+meter)");
  }
  await page.reload({ waitUntil: "networkidle" });
  const stillThree = await page.$$eval("tbody tr", (rows) =>
    rows.map((r) => r.innerText).filter((t) => /Asset age rule/.test(t)).length,
  );
  check(stillThree === 3, `still three, not six, after a second sweep (saw ${stillThree})`);

  // ═══ 4 · switch the rule Off → the sweep raises none ═════════════════════
  await page.goto(`${BASE}/${TENANT}/work/rules`, { waitUntil: "networkidle" });
  const offButton = await page.$("button[data-rule-toggle]");
  if (offButton) {
    await offButton.click();
    await page.waitForTimeout(500);
  }
  if (process.env.SMOKE_SWEEP === "auto") {
    const third = runSweep("with the rule Off");
    check(/'raised': 0/.test(third), "a rule that is Off raises nothing (BR-WRK-033)");
  }

  // ═══ 5 · the Assets door offers only templates for THIS kind of meter ════
  await page.goto(`${BASE}/${TENANT}/assets?q=${ASSET_NO}`, { waitUntil: "networkidle" });
  const assetLink = await page.$(`a:has-text("${ASSET_NO}")`);
  check(assetLink !== null, `${ASSET_NO} is on the registry`);
  if (assetLink) {
    await assetLink.click();
    await page.waitForLoadState("networkidle");
  }
  const assetUrl = page.url();
  const assetId = assetUrl.split("/assets/")[1]?.split(/[/?#]/)[0] ?? "";
  await page.goto(`${BASE}/${TENANT}/assets/${assetId}/work-orders/new`, {
    waitUntil: "networkidle",
  });
  await page.screenshot({ path: join(OUT, "Work-028.png"), fullPage: true });

  const offered = await page.$$eval("[data-raise-template] option", (els) =>
    els.map((e) => e.textContent.trim()).filter((t) => t.length > 0),
  );
  check(offered.length >= 2, `the template list is served (${offered.length} entries incl. the prompt)`);
  check(
    !offered.some((t) => /hydrant/i.test(t)),
    "a template restricted to another kind of asset is NOT offered",
  );

  // ═══ 6 · raise it → the dispatcher, and the maintenance history ══════════
  const pick = await page.$("[data-raise-template]");
  if (pick) {
    const value = await page.$eval("[data-raise-template] option:nth-child(2)", (e) => e.value);
    await pick.selectOption(value);
    await page.click("[data-raise-submit]");
    await page.waitForLoadState("networkidle");
  }

  await page.goto(`${BASE}/${TENANT}/assets/${assetId}`, { waitUntil: "networkidle" });
  const maintenanceTab = await page.$('a:has-text("Tests & maintenance"), button:has-text("Tests & maintenance")');
  if (maintenanceTab) {
    await maintenanceTab.click();
    await page.waitForLoadState("networkidle");
  }
  await page.screenshot({ path: join(OUT, "asset-maintenance-history.png"), fullPage: true });
  const historyText = await page.evaluate(() => document.body.innerText);
  check(/WO-\d{4}/.test(historyText), "the Maintenance history reads a WO- number where it read a dash");

  // ═══ 7 · the released controls, and no "Work R5" anywhere ════════════════
  const surfaces = [
    ["asset detail", `/assets/${assetId}`],
    ["retire", `/assets/${assetId}/retire`],
    ["reassign", `/assets/${assetId}/reassign`],
    ["log maintenance", `/assets/${assetId}/maintenance/new`],
    ["inventory tab", `/assets?tab=meters`],
  ];
  for (const [name, path] of surfaces) {
    await page.goto(`${BASE}/${TENANT}${path}`, { waitUntil: "networkidle" });
    const body = await page.evaluate(() => document.body.innerText);
    check(!/Work R5/.test(body), `${name}: the words "Work R5" are gone`);
    const dead = await page.$$eval("[data-work-r5]", (els) => els.length);
    check(dead === 0, `${name}: no control still carries the retired refusal hook`);
  }

  // The pre-ticks are ENABLED — an absence alone would pass over a screen that
  // simply stopped drawing them, which is why this asserts the control too.
  for (const [name, path] of surfaces.slice(1, 4)) {
    await page.goto(`${BASE}/${TENANT}${path}`, { waitUntil: "networkidle" });
    const state = await page.$$eval("[data-raise-work] input", (els) =>
      els.map((e) => ({ disabled: e.disabled })),
    );
    check(state.length === 1, `${name}: the raise-a-work-order tick is drawn`);
    // ⚠ **`state.length === 1 &&` IS LOAD-BEARING AND WAS MISSING.**
    // `[].every(...)` is TRUE, so on 2026-09-05 this line reported *"retire:
    // and it is ENABLED"* — a tick, PASSING — about a page that draws no
    // checkbox at all. A zero-result assertion that passes because nothing
    // happened is the exact shape the wave L walkthrough was bitten by; pair
    // every "it is fine" with a positive that proves the thing was there.
    check(
      state.length === 1 && state.every((s) => !s.disabled),
      `${name}: and it is ENABLED`,
    );
  }

  // And *Parts in Work →* really lands on the parts register.
  // ⚠ `?tab=inventory`, NOT `?tab=meters` — the control lives on
  // `AssetInventoryTab.tsx`, which is what its name says and what the running
  // app serves (the seven asset tabs are meters · sub_meters ·
  // behind_the_meter · inventory · lifecycle · map · imports). This script
  // asked the meters tab and reported *"Parts in Work → was not found"* on
  // 2026-09-05 over a control that was present and working one tab along.
  await page.goto(`${BASE}/${TENANT}/assets?tab=inventory`, { waitUntil: "networkidle" });
  const partsButton = await page.$("[data-parts-in-work] button");
  if (partsButton) {
    await partsButton.click();
    await page.waitForLoadState("networkidle");
    check(
      page.url().includes("/work/parts"),
      `"Parts in Work →" lands on the parts register (went to ${page.url()})`,
    );
  } else {
    check(false, '"Parts in Work →" was not found on the inventory tab');
  }

  // ═══ 8 · DEF-WRK-4098 / DEF-WRK-4119 / DEF-AST-4120 / DEF-WRK-4121 ══════
  //
  // ⚠ **THREE SHIPPED SCREENS DREW EMPTY TABLES OVER ROWS THE SERVER SENT, AND
  // A FOURTH COULD NOT RAISE A JOB. EVERY AUTOMATED CHECK WAS GREEN OVER ALL
  // FOUR.** They were found in a browser and by nothing else (hard-won law 6),
  // which is what this whole file is for — and step 1 above WOULD have caught
  // the rules half from the day it was written, except that nothing could run
  // it until `work` became a sample-data module (`DEF-WRK-4085`). A walkthrough
  // nobody can run is a plan, not a proof.
  //
  // Each block below pairs a POSITIVE with the absence it is really asserting,
  // because "the empty state is not shown" is true of a page that never loaded.

  // ── 8a · Settings → Labour rates draws its rates ────────────────────────
  await page.goto(`${BASE}/${TENANT}/settings/reference-data/work-labour-rates`, { waitUntil: "networkidle" });
  await page.screenshot({ path: join(OUT, "Work-030.png"), fullPage: true });
  await arrived(page, "Labour rates", "Work-030");

  const rateRows = await page.$$eval("tbody tr", (els) =>
    els.map((tr) => Array.from(tr.querySelectorAll("td")).map((td) => td.innerText.trim())),
  );
  const served = await page.evaluate(async (tenant) => {
    const r = await fetch(`/api/${tenant}/work/labour-rates`, { credentials: "include" });
    const body = await r.json();
    return { count: body.count ?? null, results: (body.results ?? []).length, keys: Object.keys(body) };
  }, TENANT);
  check(
    served.results > 0,
    `the API really returns rates for this tenant (count ${served.count}, keys ${served.keys.join("/")})`,
  );
  // THE DEFECT, IN ONE LINE: the table drew 0 rows while the API answered 4.
  check(
    rateRows.length === served.results,
    `every rate the API returned is on the screen (drew ${rateRows.length} of ${served.results})`,
  );
  const ratesText = await page.$eval("body", (el) => el.innerText);
  check(!/No rates set/.test(ratesText), "the empty state is NOT drawn over rows that exist");

  // ── 8b · Work-007 can raise a work order with work already on it ────────
  await page.goto(`${BASE}/${TENANT}/work/orders`, { waitUntil: "networkidle" });
  await arrived(page, "Work orders", "Work-007");
  const openRows = await page.$$eval("tbody tr", (els) => els.length);
  // ⚠ THE PAIRING THAT MATTERS. `+ New work order` used to live ONLY in the
  // table's empty state, so a check on an EMPTY list would have found it and
  // proved nothing. The list must be non-empty for this assertion to mean what
  // it says — a dispatcher's list never is.
  check(openRows > 0, `the dispatcher's list is NOT empty (${openRows} open orders)`);
  const newOrder = await page.$("[data-orders-actions] [data-new-order]");
  check(newOrder !== null, "+ New work order is on the screen WITH work already listed");
  if (newOrder) {
    const style = await newOrder.evaluate((el) => {
      const s = getComputedStyle(el);
      return { display: s.display, disabled: el.disabled, text: el.innerText.trim() };
    });
    check(style.disabled !== true, `it is not disabled (reads ${JSON.stringify(style.text)})`);
    await newOrder.click();
    await page.waitForLoadState("networkidle");
    check(
      /\/work\/orders\/new/.test(page.url()),
      `pressing it opens the wizard (went to ${page.url()})`,
    );
  }
  await page.goto(`${BASE}/${TENANT}/work/orders`, { waitUntil: "networkidle" });
  await page.screenshot({ path: join(OUT, "Work-007-actions.png"), fullPage: true });

  // ── 8c · the asset door's maintenance index survives the envelope ───────
  // `_envelope` builds a fresh four-key dict, so a view that SET an extra key
  // on the selector's result lost it silently. Ask the API directly: an empty
  // index and a dropped one render identically on the screen, which is exactly
  // how this hid.
  const assetDoor = await page.evaluate(async (tenant) => {
    const list = await fetch(`/api/${tenant}/assets?per=1`, { credentials: "include" });
    const body = await list.json();
    const id = (body.results ?? [])[0]?.id;
    if (!id) return { id: null };
    const r = await fetch(`/api/${tenant}/assets/${id}/work-orders`, { credentials: "include" });
    const wo = await r.json();
    return { id, keys: Object.keys(wo), hasIndex: "maintenance_index" in wo };
  }, TENANT);
  check(
    assetDoor.id !== null && assetDoor.hasIndex,
    `GET /assets/{id}/work-orders still carries maintenance_index (keys ${(assetDoor.keys ?? []).join("/")})`,
  );

  // ── 8d · DEF-WRK-4096 — no confident zero over a refusal ────────────────
  // Four of the five triggers cannot raise at all (the engine stamps a source
  // the writer refuses), and the sweep swallows it and reports `raised: 0`.
  // Repairing the blank table is what made that zero visible, so the column
  // must not state it as a fact. Not fixed here — see DEF-WRK-4096/4097.
  await page.goto(`${BASE}/${TENANT}/work/rules`, { waitUntil: "networkidle" });
  await arrived(page, "Rules", "Work-026");
  const thisMonth = await page.$$eval("tbody tr", (els) =>
    els.map((tr) => {
      const cells = Array.from(tr.querySelectorAll("td")).map((td) => td.innerText.trim());
      return { name: cells[0], source: cells[1], month: cells[5] };
    }),
  );
  const dashed = thisMonth.filter((r) => r.month === "—");
  check(
    dashed.length > 0,
    `THIS MONTH draws a dash, not a 0, for the ${dashed.length} rule(s) whose raises are refused`,
  );
  check(
    thisMonth.length - dashed.length > 0,
    `and a real count for the ${thisMonth.length - dashed.length} rule(s) that can raise — the column still works`,
  );

  await browser.close();
  console.log(`\nscreenshots: ${OUT}`);
  if (failures.length > 0) {
    console.log(`\n${failures.length} FAILED:`);
    for (const f of failures) console.log(`   ⛔ ${f}`);
    process.exit(1);
  }
  console.log("\nall checks passed — a rule raises jobs overnight, and one form opens from four doors");
})();
