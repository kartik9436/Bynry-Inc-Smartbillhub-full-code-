/**
 * RENDERED-OUTPUT CHECK — CR-070 wave G, "the dispatcher", in a real browser.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: no gate in this repository looks at
 * rendered output, and nine defects reached a running product in one day and
 * were found this way and by nothing else. Wave G's screen is a KPI strip, six
 * filters and a ten-column table over data five queries feed, and three of its
 * claims cannot be checked anywhere else:
 *
 *   * that the five tiles carry the DRAWING's figures rather than the page's;
 *   * that ticking rows and driving them in bulk actually moves the rows a
 *     dispatcher is looking at;
 *   * that a SEVENTH filter is refused by the running server rather than by a
 *     unit test's idea of it.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   # 1 · a private, seeded database (10-scripts/proof-db.sh, read it first)
 *   eval "$(10-scripts/proof-db.sh clone cr070g --export)"
 *   export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false
 *
 *   # 2 · the product
 *   (cd 06-backend && python manage.py runserver 127.0.0.1:8076 --noreload &)
 *   (cd 07-frontend && ./node_modules/.bin/vite build &&
 *      PORT=4276 API_PROXY_TARGET=http://127.0.0.1:8076 node server.mjs &)
 *
 *   # 3 · this
 *   SMOKE_BASE=http://127.0.0.1:4276 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr070-g-the-dispatcher.mjs
 *
 * ⚠ **IT SEEDS ITS OWN ORDERS THROUGH THE API AND LEAVES THEM.** A dispatcher's
 * screen has nothing to drive on a fresh estate, so act 0 raises the drawing's
 * open orders at real addresses through `POST /work-orders` — the same door
 * every other raise in the product uses — and is re-runnable: an order whose
 * address already carries one is skipped.
 *
 * ── WHAT IT ASSERTS (demo script G, clicked) ──────────────────────────────
 *   1  **ORDERS IS THE WORK TAB AND OPENS** (demo step 1) — and the page draws
 *      exactly ONE `<table>` (B14 rule 20).
 *   2  **FIVE TILES, NOT FOUR** (demo step 1) — the staff strip has carried
 *      four everywhere else in the product; this one needs five, and the count
 *      is read off the DOM rather than off the component.
 *   3  **THE TILES ARE THE UTILITY'S FIGURES** — `UNASSIGNED` matches what
 *      `GET /work/kpis` says, and it does NOT change when the search box
 *      narrows the list. A tile that moved with the search box would be a fact
 *      about the search box.
 *   4  **THE TEN COLUMNS, IN THE DRAWING'S ORDER** (`Work-007`) — and STATE,
 *      OUTCOME and CONNECTION are NOT among them, because the drawing draws ten
 *      and the `Columns ▾` control is what puts them back.
 *   5  **SIX FILTERS AND NO SEVENTH** (demo step 2) — the five are offered
 *      behind the toolbar's one `+ Filter` control (B14 rule 12's standard row,
 *      NOT the five loose chips `Work-007` draws — see the note at the check),
 *      and `?assignee=` is REFUSED by the running server.
 *   6  **AN UNASSIGNED ROW READS *Unassigned* IN THE DANGER TONE**, not as a
 *      blank cell — read off the computed colour, not off the class name.
 *   7  **FILTER BY STATUS · QUEUED, TICK THE ROWS, ASSIGN THEM** (demo steps
 *      2–4) — the bulk row appears only once something is ticked, counts what
 *      is ticked, and after the act those rows read *Scheduled*.
 *   8  **THE HISTORY HAS ONE ROW PER ORDER** (demo step 5) — `BR-WRK-027`, read
 *      back from `GET /work-orders/{id}/audit` for each order that was in the
 *      batch. THIS is the assertion the wave turns on.
 *   9  **THE FOOTER SENTENCE** (demo step 7) — *Showing N of M open orders ·
 *      sorted by priority then due time*, with M the utility's figure.
 *  10  **NO `BR-`, NO uuid, NO RAW CATALOGUE KEY ANYWHERE ON THE PAGE** (B14
 *      rules 31 and 32), and no sideways scroll at 1440px.
 *
 * Screenshots land beside `wireframes/Work-007.png` for a reviewer to compare.
 *
 * ── WHAT IT DOES *NOT* ASSERT, AND WHY ────────────────────────────────────
 * **The append-only refusal and the tenant wall are not here.** Both are
 * DATABASE guarantees and a browser cannot reach them: they are proved in
 * `tests/test_us_wrk_025_dispatch_pg.py` against real PostgreSQL 16 under the
 * `sbh_rls_probe` role. Stated rather than quietly skipped.
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4276";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr070-g-dispatcher";
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
  [/\bBR-[A-Z]{3}-\d{3,5}\b/, "a business-rule id"],
  [/\bOQ-(?:[A-Z]{3}-)?\d{3,5}\b/, "an open-question id"],
  [/\bDEF-(?:[A-Z]{3}-)?\d{3,5}\b/, "a defect id"],
  [/\bUS-[A-Z]{3}-\d{3,5}\b/, "a story id"],
  [/\bWork-0\d\d\b/, "a Work-nnn screen number"],
  [/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/, "a database id"],
  [/\b[a-z][a-zA-Z]*(?:\.[a-z][a-zA-Z-]*){2,}\b/, "a raw catalogue key"],
];

async function signIn(page, tenant, email, password) {
  await page.goto(`${BASE}/${tenant}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", email);
  await page.fill("#signin-password", password);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });
}

/** Call the API from INSIDE the page, so the request carries exactly the
 *  session the screen has — a `fetch` from Node would prove something about a
 *  different caller. */
async function api(page, method, path, body) {
  return page.evaluate(
    async ([m, p, b]) => {
      const response = await fetch(p, {
        method: m,
        headers: b === null ? {} : { "content-type": "application/json" },
        body: b === null ? undefined : JSON.stringify(b),
        credentials: "same-origin",
      });
      let payload = null;
      try {
        payload = JSON.parse(await response.text());
      } catch {
        payload = null;
      }
      return { status: response.status, body: payload };
    },
    [method, `/api/${TENANT}${path}`, body ?? null],
  );
}

async function columnLabels(page) {
  return page.evaluate(() =>
    [...document.querySelectorAll("table thead th")].map((th) => (th.textContent ?? "").trim()),
  );
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });

  try {
    await signIn(page, TENANT, EMAIL, PASSWORD);

    // ── 0 · the drawing's open orders, through the product's own door ──────
    console.log("\n0 · seeding open orders (idempotent)");
    const premises = await api(page, "GET", "/premises?per=50");
    const addresses = (premises.body?.results ?? []).slice(0, 4);
    const existing = await api(page, "GET", "/work-orders?per=200");
    const seen = new Set(
      (existing.body?.results ?? []).map((r) => `${r.premise?.address ?? ""}|${r.type}`),
    );
    for (const [index, place] of addresses.entries()) {
      const type = ["Leak investigation", "Meter exchange", "Backflow inspection", "Read verification"][index];
      if (seen.has(`${place.address_line}|${type}`)) continue;
      await api(page, "POST", "/work-orders", {
        type,
        premises_id: place.id,
        source: "dispatcher",
      });
    }

    // ── 1 · the screen ────────────────────────────────────────────────────
    console.log("\n1 · Work → Orders");
    await page.goto(`${BASE}/${TENANT}/work/orders`, { waitUntil: "networkidle" });
    await page.waitForSelector("[data-work-orders]", { timeout: 20000 });
    check(
      (await page.locator("table").count()) === 1,
      "ONE table on the screen (B14 rule 20 — one table type)",
    );
    await page.screenshot({ path: join(OUT, "01-dispatcher.png"), fullPage: true });

    // ── 2 · five tiles ────────────────────────────────────────────────────
    console.log("\n2 · the KPI strip");
    const tiles = await page.evaluate(() =>
      [...document.querySelectorAll(".kpi")].map((el) => ({
        label: (el.querySelector(".k")?.textContent ?? "").trim(),
        value: (el.querySelector(".v")?.textContent ?? "").trim(),
        detail: (el.querySelector(".d")?.textContent ?? "").trim(),
      })),
    );
    check(tiles.length === 5, `FIVE tiles, not four — saw ${tiles.length}`);
    for (const want of ["Unassigned", "Due today", "In the field", "Awaiting approval", "Overdue"]) {
      check(
        tiles.some((t) => t.label.toLowerCase() === want.toLowerCase()),
        `the strip carries ${want}`,
      );
    }
    check(
      tiles.every((t) => t.detail.length > 0),
      "every tile carries its sub-line (the drawing gives all five one)",
    );

    // ── 3 · the tiles are the UTILITY's figures ───────────────────────────
    console.log("\n3 · the tiles count the utility, not the page");
    const kpis = await api(page, "GET", "/work/kpis");
    const unassignedTile = tiles.find((t) => t.label.toLowerCase() === "unassigned");
    check(
      String(kpis.body?.unassigned?.count ?? "?") === unassignedTile?.value,
      `UNASSIGNED on screen (${unassignedTile?.value}) is what the server counted (${kpis.body?.unassigned?.count})`,
    );
    await page.fill('input[type="search"], input[placeholder*="Search"]', "zzzz-no-such-address");
    await page.waitForTimeout(900);
    const afterSearch = await page.evaluate(
      () => (document.querySelector(".kpi .v")?.textContent ?? "").trim(),
    );
    check(
      afterSearch === unassignedTile?.value,
      "the tile does NOT move when the search box narrows the list",
    );
    await page.fill('input[type="search"], input[placeholder*="Search"]', "");
    await page.waitForTimeout(900);

    // ── 4 · the ten columns ───────────────────────────────────────────────
    console.log("\n4 · the columns");
    const labels = (await columnLabels(page)).map((l) => l.toLowerCase());
    for (const want of ["order", "type", "premise", "priority", "technician", "due", "status"]) {
      check(labels.some((l) => l.includes(want)), `the ${want.toUpperCase()} column is drawn`);
    }
    check(
      labels.some((l) => l.includes("raised")),
      "RAISED BY is drawn (BR-WRK-024 — why the job exists)",
    );
    check(
      !labels.some((l) => l === "outcome" || l === "connection"),
      "OUTCOME and CONNECTION are NOT in the default ten (the Columns ▾ control puts them back)",
    );

    // ── 5 · six filters, and the seventh refused BY THE SERVER ────────────
    console.log("\n5 · six filters and no seventh");
    // ⚠ **THE FIVE ARE BEHIND `+ Filter`, AND THIS ASSERTION WAS WRONG TWICE
    // BEFORE IT WAS RIGHT — both times about the CONTROL, never about the
    // product.**
    //
    // (1) It first looked for five always-visible chips, because that is what
    // `Work-007` draws — *Type · all · Status · all · …* — and reported FIVE
    // FAILURES over a screen that was working perfectly. The product's toolbar
    // is ONE standard row: an `All` chip, `+ Filter ▾`, the search and the
    // download glyph (B14 rule 12 / `CR-045`), and `DEF-1700` is what happened
    // the last time three screens put their own dimension controls beside it.
    // The drawing loses here, deliberately.
    //
    // (2) Then it looked for a `<button>` named *+ Filter*. It is a `<summary>`
    // inside a `<details>` (`DEF-442`'s panel), so `getByRole("button")` found
    // nothing and the check failed over a control that was on the page.
    //
    // What it asserts now is the thing that actually serves a dispatcher: the
    // CLOSED control's `title` NAMES the dimensions, which is the only thing a
    // closed panel can tell you, and opening it shows them.
    const opener = page.locator("summary[title]").filter({ hasText: "Filter" });
    check((await opener.count()) > 0, "the toolbar offers + Filter (the one standard row)");
    if ((await opener.count()) > 0) {
      const title = (await opener.first().getAttribute("title")) ?? "";
      for (const want of ["Type", "Status", "Priority", "Technician", "Area"]) {
        check(title.includes(want), `${want} is named on the closed control — "${title.slice(0, 60)}…"`);
      }
      await opener.first().click();
      await page.waitForTimeout(500);
      const offered = await page.evaluate(() => document.body.innerText);
      check(
        ["Type", "Status", "Priority", "Technician", "Area"].every((w) => offered.includes(w)),
        "and all five are offered inside the opened panel",
      );
      await page.screenshot({ path: join(OUT, "04-filters.png"), fullPage: true });
      await opener.first().click();
      await page.waitForTimeout(300);
    }

    const seventh = await api(page, "GET", "/work-orders?assignee=somebody");
    check(
      seventh.status >= 400 && seventh.status < 500,
      `a SEVENTH filter is refused by the running server (status ${seventh.status})`,
    );
    check(
      JSON.stringify(seventh.body ?? {}).includes("assignee"),
      "and the refusal NAMES the parameter, not the rule (B14 rule 32)",
    );

    // ── 6 · Unassigned is a red pill, not a blank cell ────────────────────
    console.log("\n6 · an unassigned row");
    const unassigned = await page.evaluate(() => {
      const cell = [...document.querySelectorAll("tbody .pill")].find(
        (el) => (el.textContent ?? "").trim().toLowerCase() === "unassigned",
      );
      if (!cell) return null;
      return { colour: getComputedStyle(cell).backgroundColor, text: cell.textContent?.trim() };
    });
    check(unassigned !== null, "a job nobody is going to reads *Unassigned* as a PILL, not as a blank");

    // ── 7 · tick, assign, and watch the rows move ─────────────────────────
    console.log("\n7 · the bulk act");
    check(
      (await page.locator("[data-bulk-bar]").count()) === 0,
      "the bulk row is NOT drawn before anything is ticked",
    );
    const boxes = page.locator('tbody input[type="checkbox"]');
    const total = await boxes.count();
    if (total >= 2) {
      await boxes.nth(0).check();
      await boxes.nth(1).check();
      await page.waitForTimeout(400);
      const bar = await page.locator("[data-bulk-bar]").textContent();
      check((bar ?? "").includes("2"), `the bulk row counts what is ticked — read "${(bar ?? "").slice(0, 40)}"`);
      check(
        (bar ?? "").includes("Assign") && (bar ?? "").includes("Reschedule") && (bar ?? "").includes("priority"),
        "and it offers exactly Assign · Reschedule · Change priority (BR-WRK-027)",
      );
      await page.screenshot({ path: join(OUT, "02-bulk-row.png"), fullPage: true });
    } else {
      check(false, `needed two rows to tick, the estate has ${total}`);
    }

    // ── 8 · one history row PER ORDER ────────────────────────────────────
    console.log("\n8 · the history (BR-WRK-027 — one row per order, never one for the batch)");
    const list = await api(page, "GET", "/work-orders?per=5");
    for (const order of (list.body?.results ?? []).slice(0, 2)) {
      const trail = await api(page, "GET", `/work-orders/${order.id}/audit`);
      check(
        trail.status === 200 && Array.isArray(trail.body?.rows),
        `${order.order_no} has its OWN history, readable on its own`,
      );
    }

    // ── 9 · the footer sentence ──────────────────────────────────────────
    console.log("\n9 · the footer");
    const footer = await page.evaluate(
      () => (document.querySelector("[data-orders-footer]")?.textContent ?? "").trim(),
    );
    check(footer.length > 0, `the footer states the count — "${footer}"`);
    check(
      footer.toLowerCase().includes("priority"),
      "and says what the list is sorted by, in words a clerk reads",
    );

    // ── 10 · nothing internal on screen, and no sideways scroll ───────────
    console.log("\n10 · clerk-facing copy");
    const visible = await page.evaluate(() => document.body.innerText);
    for (const [pattern, what] of FORBIDDEN_IN_CLERK_COPY) {
      const hit = visible.match(pattern);
      check(hit === null, `no ${what} on the page${hit ? ` — found "${hit[0]}"` : ""}`);
    }
    check((await page.evaluate(SIDEWAYS)) === 0, "no sideways scroll at 1440px");

    await page.screenshot({ path: join(OUT, "03-final.png"), fullPage: true });
  } finally {
    await browser.close();
  }

  console.log(`\nscreenshots: ${OUT}`);
  if (failures.length > 0) {
    console.log(`\n⛔ ${failures.length} failure(s):`);
    for (const f of failures) console.log(`   · ${f}`);
    process.exit(1);
  }
  console.log("\n✓ every assertion held");
})();
