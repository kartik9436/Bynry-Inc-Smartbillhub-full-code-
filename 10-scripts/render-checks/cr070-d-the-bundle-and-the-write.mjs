/**
 * RENDERED-OUTPUT CHECK — CR-070 wave D, "the bundle, and the one write", in a
 * real browser. Task `D6`; demo script D; `US-WRK-013` · `014` · `015` · `018`.
 *
 * ⚠ **WHY THIS EXISTS, AND WHY IT IS LATE.** Hard-won law 6: no gate in this
 * repository looks at rendered output. Wave D's own stamp in
 * `10-execution-plan.md` says so in as many words — *"`D6` IS NOT DONE …
 * the wave is not signed off until it has run green on the built product"* —
 * and it shipped as `2.166.0` without it. This is that run.
 *
 * ⚠ **AND IT CRAWLS. IT DOES NOT TYPE ADDRESSES.** Typing `/work/templates`
 * proves the router works and proves nothing about whether a person can get
 * there. The customer portal reported all 50 screens healthy on exactly that
 * mistake and 26 of them turned out to have no door (`DEF-CWP-3925`). So every
 * screen below is reached by CLICKING: the rail's *Work*, then the strip's
 * *Templates*, then a template's own name, then its tabs and its buttons. The
 * only address typed anywhere in this file is the sign-in page.
 *
 * ⚠ **AND IT PRESSES CONTROLS RATHER THAN READING THEIR STATE.** A check that
 * asks whether Delete carries `disabled` passes on a screen where Delete is
 * disabled AND the server would have removed the template anyway. So Delete is
 * CLICKED — and the assertion is that nothing happened: no request left the
 * page and the template is still there afterwards. The other half of
 * `BR-SHL-025` (the SERVER refuses too) is proved by calling `DELETE` from the
 * page's own session, which is the half a greyed button can never show.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   # 1 · a private, seeded database (10-scripts/proof-db.sh, read it first)
 *   eval "$(10-scripts/proof-db.sh clone waved --export)"
 *   export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false
 *
 *   # 2 · the story the drawings are made of — v1, v2 and the 35 orders.
 *   #     ⚠ NOT OPTIONAL. Without it every template on a seeded database has
 *   #     one version and zero orders, and six checks below fail reading
 *   #     exactly like a broken screen.
 *   (cd 06-backend && python manage.py shell < ../10-scripts/render-checks/cr070-d-fixture.py)
 *
 *   # 3 · the product. BUILD THE BUNDLE — a stale `dist/` is the most
 *   #     expensive way to read this script's output.
 *   (cd 06-backend && ALLOWED_HOSTS='*' python manage.py runserver 127.0.0.1:8180 --noreload &)
 *   (cd 07-frontend && ./node_modules/.bin/vite build &&
 *      PORT=4380 API_PROXY_TARGET=http://127.0.0.1:8180 node server.mjs &)
 *
 *   # 4 · this
 *   SMOKE_BASE=http://127.0.0.1:4380 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr070-d-the-bundle-and-the-write.mjs
 *
 * ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** `sbh_dev` is
 * reseeded by other lanes and a mid-run reseed looks exactly like a broken
 * screen.
 *
 * ⚠ **IT MUTATES ITS DATABASE AND DOES NOT PUT IT BACK.** It duplicates a
 * template, deactivates and reactivates the copy, and publishes a draft —
 * which allocates an `ST-` number `BR-TEN-035` will never reuse. Re-run the
 * fixture (step 2) before running it a second time; the fixture is idempotent.
 *
 * ── WHAT IT ASSERTS (demo script D, clicked) ──────────────────────────────
 *   1  **THE DOOR.** The rail's *Work* opens the shell and the strip's four
 *      tabs are the shared page header's — ONE `[data-page-header-tabs]`, and
 *      the module's old `[data-work-tabs]` gone by name (`DEF-WRK-3955`).
 *      *Templates* is a real link and clicking it lands on the list.
 *   2  **`Work-013`'s NINE COLUMNS IN THE DRAWING'S ORDER**, and the CONTENTS
 *      cell reads *7 tasks · 3 parts · 3 readings* — counted in the DOM and
 *      checked against what `GET /work/templates` served, never a number typed
 *      into React.
 *   3  **TWO WATER TEMPLATES SIT TOGETHER** (`BR-WRK-010`, `WM-08`) —
 *      yesterday's `(service, sequence)` key forbade it. Read as ROWS, then
 *      narrowed with the drawing's own *Filter by service ▾* and read again.
 *   4  **THE FOOTER COUNTS THE WHOLE LIST**, against the server's own `counts`
 *      — the figure a pager cannot carry.
 *   5  **THE TEMPLATE OPENS FROM ITS OWN NAME** and `Work-022` carries the
 *      kicker *Service template · ST-nnnn · v2*, the meta *45 min · 1
 *      technician*, and an Overview that counts all seven collections.
 *   6  **THE BUNDLE IS ROWS AND THE ROWS ARE ON SCREEN** (`BR-WRK-009`,
 *      `US-WRK-014`): the safety lines, the seven steps with their minutes and
 *      their camera flags, the three parts, the three readings **each with its
 *      unit** (hard rule 3) and the help pack. ⚠ They are on the BUILDER,
 *      which the detail's own *Edit template* opens — the detail counts them.
 *      Both screens are read, in that order, by following the button.
 *   7  **VERSIONS: v2 ABOVE v1, 31 AND 4** (`US-WRK-018`, `BR-WRK-008`), with
 *      the pills *Current* / *Superseded* and the footer *35 orders raised
 *      across 2 versions — nothing was rewritten*.
 *   8  **DELETE IS REFUSED, PRESSED, AND REFUSED AGAIN BY THE SERVER**
 *      (`BR-WRK-012`, `BR-SHL-025`): the reason carries the number, the click
 *      sends nothing, and `DELETE /work/templates/{id}` from the page's own
 *      session answers a refusal with a sentence.
 *   9  **DUPLICATE AND DEACTIVATE WORK, AND THE LIST FOLLOWS**: a seventh row
 *      appears as a *Draft* with NO number, Deactivate turns it *Inactive*,
 *      the footer's three figures move, and Reactivate puts it back.
 *  10  **PUBLISH TWICE IN THE SAME SECOND MAKES ONE VERSION** (`BR-WRK-011`),
 *      fired from the page's own session at the draft the fixture left.
 *  11  **NO DATABASE ID, NO INTERNAL CODE AND NO RAW TRANSLATION KEY REACHES A
 *      CLERK** (B14 rules 31 and 32) on either screen, **THE DESCRIPTION IS
 *      CAPPED AT 80%** (rule 18) and there is **NO SIDEWAYS SCROLL AT 1440**.
 *  12  **WHAT THE DATES ACTUALLY SAY** is printed rather than asserted —
 *      `DEF-SHL-3964` is open and another lane owns it.
 *   Screenshots land in `$SMOKE_OUT` (default /tmp/cr070-d-bundle), beside
 *   which a reviewer opens `wireframes/Work-013.png` and `Work-022.png`.
 *
 * ── WHAT IT DOES *NOT* ASSERT, AND WHY ────────────────────────────────────
 * **The isolation step is not here.** Provisioning a second utility inside a
 * browser walkthrough would make this file a seeder; the wall is proved where
 * it can be proved properly — `06-backend/tests/test_us_wrk_rls_pg.py` reads
 * `pg_class` for all fourteen Work tables under a non-superuser probe role.
 * Stated here rather than quietly skipped.
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4380";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr070-d-bundle";
const VIEWPORT = { width: 1440, height: 1000 };

/** The fixture's template — `cr070-d-fixture.py`. */
const TEMPLATE = "Meter exchange — residential";
const DRAFT = "Leak investigation — walkthrough draft";

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}
function note(message) {
  console.log(`   · ${message}`);
}

const SIDEWAYS =
  "Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)";

/** `Work-013`'s columns, in the drawing's order. */
const COLUMNS = [
  "Template",
  "Service",
  "Job type",
  "Contents",
  "Gate",
  "Skill",
  "Est.",
  "Status",
  "Actions",
];

/** Anything a clerk must never be shown (B14 rules 31 and 32), plus the raw
 *  translation key `DEF-WRK-3957` found in the templates search box. */
const FORBIDDEN_IN_CLERK_COPY = [
  /\bBR-[A-Z]{3}-\d{3,5}\b/,
  /\bOQ-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /\bDEF-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /\bUS-[A-Z]{3}-\d{3,5}\b/,
  /\bWM-\d\d\b/,
  /\bWork-0\d\d\b/,
  /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
  /\bwork\.[a-z]+\.[a-zA-Z.]+\b/,
];

function clerkCopyOffences(text) {
  return FORBIDDEN_IN_CLERK_COPY.map((re) => text.match(re))
    .filter((m) => m !== null)
    .map((m) => m[0]);
}

async function signIn(page, tenant, email, password) {
  await page.goto(`${BASE}/${tenant}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", email);
  await page.fill("#signin-password", password);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });
}

/** Every row of the templates table, as the columns the drawing names. */
async function tableRows(page) {
  return page.$$eval('[data-work-templates=""] tbody tr', (rows) =>
    rows.map((tr) => {
      const cells = [...tr.querySelectorAll("td")].map((td) => td.innerText.trim());
      return {
        name: (tr.querySelector("td a")?.innerText ?? cells[0] ?? "").trim(),
        template: cells[0] ?? "",
        service: cells[1] ?? "",
        jobType: cells[2] ?? "",
        contents: cells[3] ?? "",
        gate: cells[4] ?? "",
        skill: cells[5] ?? "",
        est: cells[6] ?? "",
        status: cells[7] ?? "",
      };
    }),
  );
}

/** Every control on the page that refuses, with the reason it gives. */
async function refusals(page) {
  return page.$$eval("button[disabled], a[aria-disabled='true']", (nodes) =>
    nodes.map((n) => ({
      label: (n.innerText || n.getAttribute("aria-label") || "").trim(),
      reason: n.getAttribute("title") ?? "",
    })),
  );
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });
  // Every request the browser could not complete, NAMED. A console line that
  // says only `ERR_CONNECTION_RESET` tells a reader nothing about which door
  // failed, and a screen missing one panel looks identical to one that is fine.
  const brokenRequests = [];
  page.on("requestfailed", (r) =>
    brokenRequests.push(`${r.method()} ${r.url()} — ${r.failure()?.errorText ?? "?"}`),
  );

  // The server's own answers, captured rather than inferred.
  let servedList = null;
  let servedDetail = null;
  let servedVersions = null;
  const deletesSeen = [];
  page.on("request", (r) => {
    if (r.method() === "DELETE" && /\/work\/templates\//.test(r.url())) deletesSeen.push(r.url());
  });
  page.on("response", async (response) => {
    const url = response.url();
    try {
      if (/\/work\/templates(?:\?|$)/.test(url)) servedList = JSON.parse(await response.text());
      else if (/\/work\/templates\/[0-9a-f-]+\/versions$/.test(url))
        servedVersions = JSON.parse(await response.text());
      else if (/\/work\/templates\/[0-9a-f-]+$/.test(url) && response.request().method() === "GET")
        servedDetail = JSON.parse(await response.text());
    } catch {
      // a redirect or a non-JSON body has nothing to read
    }
  });

  console.log(`cr070-d: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);

  await signIn(page, TENANT, EMAIL, PASSWORD);
  console.log("   signed in as Dana (the owner login)");

  // ═════════════════════════════════════════════════════════════════════════
  // 1 · THE DOOR — the rail, then the strip. NOTHING IS TYPED.
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── the way in: rail → Work → Templates ──");
  const railWork = page.locator("a.side-item", { hasText: /^Work$/ }).first();
  // ⚠ WAIT FOR IT BEFORE COUNTING. `waitForURL` returns when the address
  // changes, which is before the shell has painted; a bare `count()` here
  // answers 0 and fails a rail that is about to be perfectly fine. The click
  // below auto-waits, so the count was the only thing racing.
  await railWork.waitFor({ state: "visible", timeout: 20000 });
  check((await railWork.count()) === 1, "the rail carries a Work entry");
  await railWork.click();
  await page.waitForURL(/\/work(\/|$)/, { timeout: 20000 });
  await page.waitForSelector("[data-work-shell]", { timeout: 20000 });
  note(`the rail landed on ${new URL(page.url()).pathname}`);

  const strips = await page.locator("[data-page-header-tabs]").count();
  check(strips === 1, `exactly one tab strip on the Work shell (found ${strips})`);
  const ownStrip = await page.locator("[data-work-tabs]").count();
  check(
    ownStrip === 0,
    `the module's own boxed strip is gone by name (found ${ownStrip} — DEF-WRK-3955)`,
  );
  const tabIds = await page.$$eval("[data-page-header-tabs] [data-tab]", (ns) =>
    ns.map((n) => n.getAttribute("data-tab")),
  );
  check(
    tabIds.join(",") === "orders,approvals,parts,templates",
    `the four tabs, in the inventory's order: ${tabIds.join(" · ")}`,
  );
  const tabsAreLinks = await page.$$eval("[data-page-header-tabs] [data-tab]", (ns) =>
    ns.every((n) => n.tagName === "A" && n.getAttribute("href")),
  );
  check(tabsAreLinks, "every Work tab is a real link a person can ⌘-click");

  await page.click('[data-page-header-tabs] [data-tab="templates"]');
  await page.waitForSelector('[data-work-templates=""]', { timeout: 20000 });
  await page.waitForSelector('[data-work-templates=""] tbody tr', { timeout: 20000 });
  check(
    new URL(page.url()).pathname === `/${TENANT}/work/templates`,
    `clicking the Templates tab landed on ${new URL(page.url()).pathname}`,
  );
  await page.screenshot({ path: join(OUT, "work-013-templates.png"), fullPage: true });

  // ═════════════════════════════════════════════════════════════════════════
  // 2 · `Work-013` — the head, the columns, and the CONTENTS sentence
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── Work-013: the list ──");
  const kicker = (await page.locator(".page-header-kicker, [class*='kicker']").first().innerText())
    .trim()
    .toUpperCase();
  check(kicker.includes("WORK"), `the kicker reads ${kicker || "(nothing)"}`);
  const title = (await page.locator("h1").first().innerText()).trim();
  check(title === "Work order templates", `the title reads "${title}"`);

  const headers = (await page.$$eval('[data-work-templates=""] thead th', (ns) =>
    ns.map((n) => n.innerText.trim()),
  )).filter((h) => h !== "");
  // ⚠ COMPARED CASE-INSENSITIVELY ON PURPOSE. The kit's header tier is
  // `text-transform: uppercase`, so `innerText` answers TEMPLATE where the
  // catalogue holds "Template". Asserting the shouted form would pin a CSS
  // decision into a content check and go red the day rule 20's tier changes.
  check(
    headers.join(" · ").toUpperCase() === COLUMNS.join(" · ").toUpperCase(),
    `the nine columns in the drawing's order — got: ${headers.join(" · ")}`,
  );

  const rows = await tableRows(page);
  // ⚠ CAPTURED NOW, BEFORE ANYTHING IS FILTERED. React Query serves the
  // unfiltered list from its cache when the filter is cleared again, so the
  // LAST answer on the wire is the filtered one — reading `servedList` after
  // section 3 compares the footer against the wrong set and fails a screen
  // that is right.
  const unfilteredList = servedList;
  check(rows.length > 0, `the list drew ${rows.length} row(s)`);
  check(
    servedList !== null && servedList.results.length === rows.length,
    `the DOM's ${rows.length} row(s) match the ${servedList?.results?.length ?? "?"} the server sent`,
  );

  const exchange = rows.find((r) => r.name === TEMPLATE);
  check(exchange !== undefined, `"${TEMPLATE}" is in the list`);
  if (exchange !== undefined) {
    check(
      exchange.contents === "7 tasks · 3 parts · 3 readings",
      `its CONTENTS cell reads "${exchange.contents}"`,
    );
    check(
      /^ST-\d{4}$/m.test(exchange.template.split("\n").pop() ?? ""),
      `the visible reference under the name is a number, not an id: "${exchange.template.replace(/\n/g, " / ")}"`,
    );
    check(exchange.est === "45 min", `EST. carries its unit: "${exchange.est}"`);
    check(exchange.status === "Published", `STATUS reads "${exchange.status}"`);
  }

  // ── a DRAFT has no number at all, and the cell says so rather than inventing one
  const draftRow = rows.find((r) => r.name === DRAFT);
  check(draftRow !== undefined, `the draft "${DRAFT}" is in the list`);
  if (draftRow !== undefined) {
    check(
      !/ST-\d{4}/.test(draftRow.template),
      `a draft draws NO ST- number: "${draftRow.template.replace(/\n/g, " / ")}"`,
    );
    check(draftRow.status === "Draft", `and its STATUS reads "${draftRow.status}"`);
  }

  // ═════════════════════════════════════════════════════════════════════════
  // 3 · TWO WATER TEMPLATES AT ONCE — WM-08, the relaxed key
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── WM-08: more than one template per service ──");
  const water = rows.filter((r) => r.service === "Water");
  check(
    water.length >= 2,
    `${water.length} Water template(s) sit in one list: ${water.map((r) => r.name).join(" · ")}`,
  );

  // the drawing's own control, PRESSED rather than read
  await page.click(".data-table-frame details summary");
  const waterBox = page.locator(".data-table-frame details label", { hasText: /^Water$/ }).first();
  check((await waterBox.count()) === 1, "the filter panel offers Water");
  await waterBox.click();
  await page.waitForFunction(
    (n) => document.querySelectorAll('[data-work-templates=""] tbody tr').length === n,
    water.length,
    { timeout: 20000 },
  ).catch(() => {});
  const filtered = await tableRows(page);
  check(
    filtered.length === water.length && filtered.every((r) => r.service === "Water"),
    `filtering by Water narrows the list to ${filtered.length} row(s), all Water`,
  );
  await page.screenshot({ path: join(OUT, "work-013-filtered-water.png"), fullPage: true });
  await waterBox.click(); // put it back
  await page.waitForFunction(
    (n) => document.querySelectorAll('[data-work-templates=""] tbody tr').length === n,
    rows.length,
    { timeout: 20000 },
  ).catch(() => {});

  // ═════════════════════════════════════════════════════════════════════════
  // 4 · THE FOOTER counts the WHOLE list, not the page in hand
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── the footer, against the server's own counts ──");
  const footer = (await page.locator('[data-templates-footer=""]').innerText()).trim();
  const counts = unfilteredList?.counts ?? null;
  check(counts !== null, "the server sent the three counts");
  if (counts !== null) {
    check(
      footer === `${counts.published} published · ${counts.draft} draft · ${counts.inactive} inactive`,
      `the footer reads "${footer}" and the server counted ${JSON.stringify(counts)}`,
    );
  }

  // ═════════════════════════════════════════════════════════════════════════
  // 5 · OPEN IT FROM ITS OWN NAME — `Work-022`
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── Work-022: the detail, opened by clicking the name ──");
  await page.click(`[data-work-templates=""] tbody tr a:text-is("${TEMPLATE}")`);
  await page.waitForSelector('[data-work-template-detail=""]', { timeout: 20000 });
  const detailPath = new URL(page.url()).pathname;
  const templateId = detailPath.split("/").pop();
  note(`the name opened ${detailPath}`);
  await page.screenshot({ path: join(OUT, "work-022-overview.png"), fullPage: true });

  const detailKicker = (await page.locator(".page-header-kicker, [class*='kicker']").first().innerText()).trim();
  check(
    /Service template · ST-\d{4} · v2/i.test(detailKicker),
    `the kicker reads "${detailKicker}"`,
  );
  check(
    !detailKicker.includes(templateId ?? "@"),
    "and it carries no database id (B14 rule 31)",
  );
  const detailTitle = (await page.locator("h1").first().innerText()).trim();
  check(detailTitle === TEMPLATE, `the title reads "${detailTitle}"`);
  const meta = (await page.locator(".page-header-rollup").first().innerText()).trim();
  check(meta === "45 min · 1 technician", `the meta reads "${meta}"`);

  const overviewFacts = await page.$$eval("[data-work-template-detail] dt, [data-work-template-detail] .fact-label", (ns) =>
    ns.map((n) => n.innerText.trim()),
  );
  const overviewText = await page.locator('[data-work-template-detail=""]').innerText();
  for (const [label, want] of [
    ["Safety lines", 3],
    ["Tasks", 7],
    ["Materials", 3],
    ["Readings", 3],
    ["Help entries", 3],
  ]) {
    const re = new RegExp(`${label}\\s*\\n?\\s*${want}\\b`);
    check(re.test(overviewText), `Overview counts ${label}: ${want}`);
  }
  if (overviewFacts.length > 0) note(`Overview facts: ${overviewFacts.join(" · ")}`);

  // ═════════════════════════════════════════════════════════════════════════
  // 6 · THE BUNDLE IS ROWS, AND THE ROWS ARE ON THE BUILDER
  //     `Work-022`'s Overview COUNTS the seven collections; the rows
  //     themselves are the eight-step builder's, which this screen's own
  //     `Edit template` opens. So: follow the button (law 2's mirror — a
  //     control that points somewhere real).
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── BR-WRK-009: the bundle, followed through Edit template ──");
  const edit = page.locator('[data-edit-template=""]');
  check((await edit.count()) === 1, "Edit template is on the detail");
  const editHref = await edit.getAttribute("href");
  check(
    editHref === `/${TENANT}/work/templates/${templateId}/edit`,
    `and it points at ${editHref}`,
  );
  await edit.click();
  await page.waitForURL(/\/edit(\?|$)/, { timeout: 20000 });
  await page.waitForSelector('[data-wizard="frame"]', { timeout: 20000 });
  await page.screenshot({ path: join(OUT, "work-014-builder-step1.png"), fullPage: true });
  const builderText = await page.evaluate(() => document.body.innerText);
  check(
    !/not built yet|still being decided|opens with the next release/i.test(builderText),
    "Edit template opens the builder, not a stated absence",
  );
  const railSteps = await page.locator('[data-wizard-step]').count();
  check(railSteps === 8, `the builder's rail draws ${railSteps} steps`);

  /** Walk the wizard the way a person does — its own Continue — and collect
   *  the visible text of every step. NOT `?step=N` typed into the address bar:
   *  that is the shortcut this whole file exists to refuse. The final step's
   *  commit is never pressed; walking to Review is reading, publishing is not. */
  const stepText = [];
  for (let step = 1; step <= 8; step += 1) {
    await page.waitForSelector('[data-wizard="content"]', { timeout: 20000 });
    await page.waitForTimeout(350);
    stepText.push(await page.evaluate(() => document.querySelector('[data-wizard="content"]').innerText));
    if (step === 8) break;
    const cont = page.locator('[data-wizard="actions"] button', { hasText: /^(Continue|Next)/ }).first();
    if ((await cont.count()) === 0) {
      check(false, `the builder has no Continue on step ${step} — the walk stopped there`);
      break;
    }
    await cont.click();
    await page.waitForFunction(
      (want) => new URLSearchParams(location.search).get("step") === String(want),
      step + 1,
      { timeout: 20000 },
    ).catch(() => {});
    if (step === 4) {
      await page.screenshot({ path: join(OUT, "work-016-builder-readings.png"), fullPage: true });
    }
  }
  check(
    stepText.length === 8,
    `Continue walked ${stepText.length} of the eight steps without typing an address`,
  );
  const all = stepText.join("\n");
  check(/Gloves and eye protection/.test(all), "the safety lines are on the builder");
  check(
    /Apply tamper seal/.test(all) && /Fit the new meter/.test(all),
    "the seven steps are on the builder, in the order the bundle holds them",
  );
  check(/\b15\b/.test(all) && /\b12\b/.test(all), "each step carries its minutes");
  check(
    /Water meter 5\/8 in|MTR-W58/.test(all),
    "the parts the template plans are on the builder",
  );
  check(
    /gal/.test(all) && /psi/.test(all),
    "each reading carries its unit (hard rule 3): gal · psi",
  );
  check(
    /Meter exchange method statement|Control room/.test(all),
    "the help pack — the document and the phone number — is on the builder",
  );
  await page.screenshot({ path: join(OUT, "work-017-builder-review.png"), fullPage: true });

  // ═════════════════════════════════════════════════════════════════════════
  // 7 · VERSIONS — v2 above v1, and the count that proves BR-WRK-008
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── Work-022 Versions: v2 above v1 ──");
  // Out of the builder the way a person leaves it — its own back link.
  const builderBack = page.locator("a.page-header-back").first();
  check((await builderBack.count()) === 1, "the builder carries its own back link");
  if ((await builderBack.count()) > 0) {
    await builderBack.click();
    await page.waitForTimeout(800);
  }
  if (!/\/work\/templates$/.test(new URL(page.url()).pathname)) {
    note(`the builder's back link landed on ${new URL(page.url()).pathname}`);
  }
  await page.waitForSelector('[data-work-templates=""] tbody tr', { timeout: 20000 }).catch(() => {});
  await page.click(`[data-work-templates=""] tbody tr a:text-is("${TEMPLATE}")`);
  await page.waitForSelector('[data-work-template-detail=""]', { timeout: 20000 });
  check(
    new URL(page.url()).pathname === detailPath,
    `back out of the builder and into the detail again (${new URL(page.url()).pathname})`,
  );
  await page.click('[data-page-header-tabs] [data-tab="versions"]');
  await page.waitForSelector('[data-template-versions=""]', { timeout: 20000 });
  await page.screenshot({ path: join(OUT, "work-022-versions.png"), fullPage: true });

  const versionRows = await page.$$eval('[data-template-versions=""] tbody tr', (trs) =>
    trs.map((tr) => [...tr.querySelectorAll("td")].map((td) => td.innerText.trim())),
  );
  check(versionRows.length === 2, `the Versions table has ${versionRows.length} row(s)`);
  if (versionRows.length === 2) {
    check(versionRows[0][0] === "v2", `the first row is ${versionRows[0][0]}`);
    check(versionRows[1][0] === "v1", `the second is ${versionRows[1][0]}`);
    check(versionRows[0][3] === "31", `v2 raised ${versionRows[0][3]} order(s)`);
    check(versionRows[1][3] === "4", `v1 still reads ${versionRows[1][3]} order(s) — nothing was rewritten`);
    check(versionRows[0][4] === "Current", `v2 is ${versionRows[0][4]}`);
    check(versionRows[1][4] === "Superseded", `v1 is ${versionRows[1][4]}`);
    check(
      versionRows[0][2] === "Added Apply tamper seal",
      `WHAT CHANGED is whatever the publisher typed: "${versionRows[0][2]}"`,
    );
    note(`PUBLISHED renders as: v2 "${versionRows[0][1]}" · v1 "${versionRows[1][1]}"`);
  }
  const versionsFooter = (await page.locator('[data-template-versions-footer=""]').innerText()).trim();
  check(
    versionsFooter === "35 orders raised across 2 versions — nothing was rewritten",
    `the footer reads "${versionsFooter}"`,
  );
  check(
    servedVersions !== null && servedVersions.orders_raised === 35,
    `and the server counted ${servedVersions?.orders_raised ?? "?"} orders`,
  );

  // Usage says the same thing in one sentence
  await page.click('[data-page-header-tabs] [data-tab="usage"]');
  await page.waitForSelector('[data-template-usage=""]', { timeout: 20000 });
  const usage = (await page.locator('[data-template-usage=""]').innerText()).trim();
  check(usage === "35 orders raised across 2 versions", `Usage reads "${usage}"`);

  // ═════════════════════════════════════════════════════════════════════════
  // 8 · DELETE — refused with the number, PRESSED, and refused by the server
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── BR-WRK-012: Delete is refused, and the server refuses too ──");
  const deleteBtn = page.locator("button", { hasText: /^Delete$/ }).first();
  check((await deleteBtn.count()) === 1, "Delete is on the detail");
  const deleteReason = await deleteBtn.getAttribute("title");
  check(
    deleteReason === "35 work orders came from this template.",
    `its reason carries the number: "${deleteReason}"`,
  );
  const deleteVariant = await deleteBtn.getAttribute("data-variant");
  check(deleteVariant === "danger", `Delete alone takes the danger tier (${deleteVariant})`);
  // B14 rule 6 — read from COMPUTED STYLE, because a utility that did not
  // compile renders as nothing while `data-variant="danger"` is still in the DOM.
  const dangerColour = await deleteBtn.evaluate((n) => getComputedStyle(n).color);
  check(
    dangerColour !== "rgb(0, 0, 0)" && dangerColour !== "",
    `and the tier actually painted (colour ${dangerColour})`,
  );

  // PRESSED. Not read.
  const deletesBefore = deletesSeen.length;
  await deleteBtn.click({ force: true });
  await page.waitForTimeout(1000);
  check(
    deletesSeen.length === deletesBefore,
    `pressing Delete sent ${deletesSeen.length - deletesBefore} request(s) — a refusal that refuses`,
  );
  check(
    (await page.locator("h1").first().innerText()).trim() === TEMPLATE,
    "and the template is still on screen afterwards",
  );

  // The half a greyed button can never prove: the SERVER says no.
  const serverRefusal = await page.evaluate(async (id) => {
    const r = await fetch(`/api/${location.pathname.split("/")[1]}/work/templates/${id}`, {
      method: "DELETE",
      headers: { "content-type": "application/json" },
    });
    let body = null;
    try {
      body = await r.json();
    } catch {
      body = null;
    }
    return { status: r.status, body };
  }, templateId);
  check(
    serverRefusal.status >= 400 && serverRefusal.status < 500,
    `DELETE from the page's own session answered ${serverRefusal.status}`,
  );
  const refusalSentence =
    serverRefusal.body?.error?.message ??
    serverRefusal.body?.message ??
    JSON.stringify(serverRefusal.body ?? {});
  note(`the server's sentence: ${String(refusalSentence).slice(0, 160)}`);
  check(
    /\b35\b/.test(JSON.stringify(serverRefusal.body ?? {})),
    "and it names the 35 orders rather than saying 'cannot delete'",
  );

  // ═════════════════════════════════════════════════════════════════════════
  // 9 · DUPLICATE and DEACTIVATE — pressed, and the list follows
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── US-WRK-015: Duplicate, Deactivate, Reactivate ──");
  const duplicate = page.locator("button", { hasText: /^Duplicate$/ }).first();
  check(
    (await duplicate.isEnabled()) === true,
    "Duplicate is offered rather than refused",
  );
  await duplicate.click();
  await page.waitForTimeout(1500);

  // `Work-022` is NOT inside the Work strip — a record detail sits under its
  // own `← Templates` (`DEF-WRK-3724`), so that link is the way home.
  const backHome = page.locator("a.page-header-back").first();
  check((await backHome.count()) === 1, "the detail carries its own ← Templates link");
  await backHome.click();
  await page.waitForSelector('[data-work-templates=""] tbody tr', { timeout: 20000 });
  await page.waitForTimeout(500);
  const afterDup = await tableRows(page);
  check(
    afterDup.length === rows.length + 1,
    `the list grew from ${rows.length} to ${afterDup.length} row(s)`,
  );
  const copy = afterDup.find((r) => r.name.startsWith(TEMPLATE) && r.name !== TEMPLATE);
  check(copy !== undefined, `the copy is in the list as "${copy?.name ?? "(missing)"}"`);
  check(copy?.status === "Draft", `and it is a ${copy?.status} — never published, so no number`);
  check(
    copy !== undefined && !/ST-\d{4}/.test(copy.template),
    "the copy carries no ST- number",
  );
  const footerAfterDup = (await page.locator('[data-templates-footer=""]').innerText()).trim();
  note(`the footer now reads "${footerAfterDup}"`);
  await page.screenshot({ path: join(OUT, "work-013-after-duplicate.png"), fullPage: true });

  // open the copy and deactivate it
  await page.click(`[data-work-templates=""] tbody tr a:text-is("${copy?.name}")`);
  await page.waitForSelector('[data-work-template-detail=""]', { timeout: 20000 });
  const noVersions = await page.locator('[data-template-versions=""]').count();
  await page.click('[data-page-header-tabs] [data-tab="versions"]');
  await page.waitForTimeout(500);
  const draftSentence = await page.locator('[data-template-no-versions=""]').count();
  check(
    draftSentence === 1 && noVersions === 0,
    "a draft's Versions tab says it has not been published yet",
  );

  const deactivate = page.locator("button", { hasText: /^Deactivate$/ }).first();
  check((await deactivate.count()) === 1, "Deactivate is on the copy");
  await deactivate.click();
  await page.waitForFunction(
    () => /Inactive/.test(document.querySelector("h1")?.parentElement?.innerText ?? ""),
    null,
    { timeout: 20000 },
  ).catch(() => {});
  const pill = await page.evaluate(() => document.body.innerText.includes("Inactive"));
  check(pill, "pressing Deactivate turns the status pill Inactive");
  const reactivate = page.locator("button", { hasText: /^Reactivate$/ }).first();
  check((await reactivate.count()) === 1, "and the button becomes Reactivate — the pair swap");
  await page.screenshot({ path: join(OUT, "work-022-inactive.png"), fullPage: true });
  await reactivate.click();
  await page.waitForTimeout(1200);
  check(
    (await page.locator("button", { hasText: /^Deactivate$/ }).count()) === 1,
    "and Reactivate puts it back",
  );

  // ═════════════════════════════════════════════════════════════════════════
  // 10 · PUBLISH TWICE IN THE SAME SECOND → ONE VERSION (BR-WRK-011)
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── BR-WRK-011: publish is the ONE write ──");
  // ⚠ **TWO HALVES, AND THEY ANSWER DIFFERENTLY.** The demo says *"publish the
  // same draft twice within a second → one version"*. That sentence has two
  // readings and the product only satisfies one of them, so both are asserted
  // here rather than whichever one happens to pass:
  //
  //   (a) SEQUENTIAL — the second press lands after the first answers. This is
  //       what a person gets through the builder, whose commit button is
  //       single-flighted by `WizardFrame`.
  //   (b) SIMULTANEOUS — both requests in flight at once. Two people on the
  //       same draft, or one impatient double-click that outruns the round
  //       trip.
  //
  // `publish` decides by READING the newest `updated_at` and comparing it with
  // the newest version row. With no version row committed yet there is nothing
  // to compare against, so (b) has no guard at all.
  const publishTwice = await page.evaluate(async (draftName) => {
    const tenant = location.pathname.split("/")[1];
    const api = (path, init) =>
      fetch(`/api/${tenant}${path}`, {
        headers: { "content-type": "application/json" },
        ...init,
      });
    const unwrap = (x) => x?.data ?? x;
    const tasks = {
      rows: [
        { title: "Find the leak", est_minutes: 20, photo_required: true, is_mandatory: true },
        { title: "Make safe", est_minutes: 10, photo_required: false, is_mandatory: true },
      ],
    };
    const put = (id) =>
      api(`/work/templates/${id}/tasks`, { method: "PUT", body: JSON.stringify(tasks) });
    const publish = (id) =>
      api(`/work/templates/${id}/publish`, {
        method: "POST",
        body: JSON.stringify({ change_note: "First publish" }),
      }).then((r) => r.json());
    const versionsOf = async (id) =>
      unwrap(await (await api(`/work/templates/${id}/versions`)).json()).versions ?? [];

    // (a) the fixture's draft, pressed twice in a row
    const list = unwrap(await (await api("/work/templates?per=200")).json());
    const draft = (list.results ?? []).find((r) => r.name === draftName);
    if (draft === undefined) return { error: "the fixture's draft is not in the list" };
    await put(draft.id);
    await publish(draft.id);
    await publish(draft.id);
    const sequential = await versionsOf(draft.id);
    const afterSeq = unwrap(await (await api(`/work/templates/${draft.id}`)).json());

    // (b) a second draft, through the product's own door, pressed twice at once
    const madeRaw = await (
      await api("/work/templates", {
        method: "POST",
        body: JSON.stringify({
          name: `${draftName} — at once ${Date.now()}`,
          service: "water",
          scope: "per_premise",
        }),
      })
    ).json();
    const made = unwrap(madeRaw);
    if (!made?.id) return { error: `POST /work/templates answered ${JSON.stringify(madeRaw).slice(0, 200)}` };
    await put(made.id);
    await Promise.all([publish(made.id), publish(made.id)]);
    const simultaneous = await versionsOf(made.id);
    const afterSim = unwrap(await (await api(`/work/templates/${made.id}`)).json());

    return {
      sequential: sequential.length,
      sequentialVersion: afterSeq.version,
      sequentialNo: afterSeq.template_no,
      simultaneous: simultaneous.length,
      simultaneousVersion: afterSim.version,
      simultaneousNo: afterSim.template_no,
      notes: simultaneous.map((v) => `v${v.version} "${v.change_note}"`),
    };
  }, DRAFT);

  if (publishTwice.error) {
    check(false, publishTwice.error);
  } else {
    check(
      publishTwice.sequential === 1,
      `(a) two presses one after the other left ${publishTwice.sequential} version — the draft is now v${publishTwice.sequentialVersion} · ${publishTwice.sequentialNo}`,
    );
    check(
      /^ST-\d{4}$/.test(publishTwice.sequentialNo ?? ""),
      `and exactly one number was allocated: ${publishTwice.sequentialNo}`,
    );
    check(
      publishTwice.simultaneous === 1,
      `(b) two presses in the SAME instant left ${publishTwice.simultaneous} version(s) — the draft is now v${publishTwice.simultaneousVersion} (${publishTwice.notes.join(" · ")})`,
    );
  }

  // ═════════════════════════════════════════════════════════════════════════
  // 11 · B14 — no id, no code, no raw key, the 80% cap, no sideways scroll
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── B14 rules 18, 20, 31, 32 ──");
  for (const [label, path] of [
    ["the list", `/${TENANT}/work/templates`],
    ["the detail", detailPath],
  ]) {
    await page.goto(`${BASE}${path}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(600);
    const text = await page.evaluate(() => document.body.innerText);
    const offences = clerkCopyOffences(text);
    check(
      offences.length === 0,
      `${label}: nothing a clerk must not see${offences.length ? ` — found ${offences.join(", ")}` : ""}`,
    );
    const overflow = await page.evaluate(SIDEWAYS);
    check(overflow === 0, `${label}: no sideways scroll at 1440 (overflow ${overflow}px)`);
    const tableKinds = await page.evaluate(() =>
      [...document.querySelectorAll("table")].map((t) => t.className || "(no class)"),
    );
    check(
      tableKinds.every((c) => /data-table|plain-table/.test(c)),
      `${label}: every table is one of the kit's two (${tableKinds.join(" · ") || "none"})`,
    );
  }

  await page.goto(`${BASE}/${TENANT}/work/templates`, { waitUntil: "networkidle" });
  const descCap = await page.evaluate(() => {
    const p = document.querySelector(".page-header-explainer");
    if (p === null) return null;
    return {
      text: p.innerText.trim().slice(0, 60),
      width: Math.round(p.getBoundingClientRect().width),
      page: Math.round(document.documentElement.clientWidth),
      max: getComputedStyle(p).maxWidth,
    };
  });
  check(descCap !== null, "the one sentence is the tab's explainer");
  if (descCap !== null) {
    check(
      descCap.width <= descCap.page * 0.8 + 1,
      `and it is capped at 80% — ${descCap.width}px of ${descCap.page}px (max-width ${descCap.max})`,
    );
  }

  // ═════════════════════════════════════════════════════════════════════════
  // 12 · WHAT IS STILL HELD, AND WHAT THE DATES SAY — reported, not asserted
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── what is still refused on these two screens ──");
  for (const [label, path] of [
    ["Work-013", `/${TENANT}/work/templates`],
    ["Work-022", detailPath],
  ]) {
    await page.goto(`${BASE}${path}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(600);
    const held = await refusals(page);
    if (held.length === 0) note(`${label}: nothing is refused`);
    for (const h of held) note(`${label}: "${h.label}" is refused — "${h.reason}"`);
  }
  await page.goto(`${BASE}${detailPath}?tab=audit`, { waitUntil: "networkidle" });
  const audit = await page.locator('[data-template-audit-absent=""]').count();
  note(`Work-022's Audit tab states an absence in one sentence: ${audit === 1 ? "yes" : "NO"}`);

  if (brokenRequests.length > 0) {
    console.log("\n── requests the browser could not complete ──");
    for (const r of [...new Set(brokenRequests)]) note(r);
  }

  await browser.close();

  console.log(`\nscreenshots: ${OUT}`);
  if (failures.length > 0) {
    console.log(`\n⛔ ${failures.length} failure(s)`);
    for (const f of failures) console.log(`   · ${f}`);
    process.exit(1);
  }
  console.log("\n✓ cr070 wave D: the bundle is rows, and publish is the one write");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-WRK-013/014/015/018@3be2d9fd (EP-WRK-03) · 10-execution-plan.md wave D task D6 · wireframes/Work-013.png · Work-022.png
// generated: 2026-09-05 by the Work walkthrough lane
// checklist: A=n/a(a check, not product code) B=n/a C✔ D✔ E=n/a F✔ G✔ H=n/a
// gates: hard-won law 6 — this IS the instrument. Proved by running it against the built bundle at 3be2d9fd; every failure it reports is quoted in the lane report.
// exceptions: E3 the tenant wall is not clicked here — it is proved on PostgreSQL by tests/test_us_wrk_rls_pg.py, and seeding a second utility inside a walkthrough would make this file a seeder (the posture cr070-o takes for the same reason)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
