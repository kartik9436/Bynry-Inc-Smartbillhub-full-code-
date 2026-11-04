/**
 * RENDERED-OUTPUT CHECK — CR-070 wave C, "Settings tells the truth", in a real
 * browser.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: no gate in this repository looks at
 * rendered output, and nine defects in one day were found this way and by
 * nothing else. PO ruling 2026-09-03: *"ensure you do web walkthorugh before
 * you sign off the user story or build"* — and, the same day, *"for Cr68, 69
 * and 70 - you will have to ensure you refer to screenshot we build and not
 * just r10"*. The reference is `04-docs/05-modules/16-work/wireframes/
 * Work-025.png` read through `08-screen-layouts.md`.
 *
 * ⚠ **AND THE DRAWING IS THE THING THIS SCREEN DELIBERATELY DOES NOT MATCH.**
 * `Work-025.png` draws a STOCK register — *`MTR-W58 · Water meter 5/8" · Yard ·
 * On hand 184 · Reorder at 60 · In cover`*, the same part on *Van 12* as a
 * second row, and a banner reading *"Reorder — 2 parts at or below reorder
 * level"*. Every specification card for the same feature says the opposite:
 * *"No stock levels, no reorder points"*. The contradiction is `DEF-WRK-3550`;
 * whether such a table may exist at all is `OQ-WRK-1490`, OPEN. **So the checks
 * below are written as ABSENCES** — a walkthrough that only asserted what IS on
 * screen would pass just as happily on a screen that had quietly grown the
 * three forbidden columns back.
 *
 * ⚠ **B14 RULE 21 MAKES A BROWSER UNAVOIDABLE HERE.** A Tailwind utility is
 * emitted ONLY for a file listed in `07-frontend/src/styles/route-b-migrated.txt`,
 * and ONLY for a token the app's theme declares — `tailwind.css` zeroes the
 * default palette, so `bg-white` or `text-slate-500` compile to NOTHING while
 * `tsc`, eslint and `toContain("flex")` all pass. `PartsPage.tsx`,
 * `AddPartModal.tsx` and `SegmentedControl.tsx` were added to that list in the
 * commit that created them; step 6 reads computed style in a real engine to
 * prove the segmented control actually painted.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   # A seeded database in under a second — read 10-scripts/proof-db.sh first.
 *   eval "$(10-scripts/proof-db.sh clone cr070c)"     # prints DATABASE_URL
 *   export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false
 *   (cd 06-backend && python manage.py migrate --no-input)   # work/0001 + 0002
 *   (cd 06-backend && python manage.py runserver 127.0.0.1:8070 --noreload &)
 *   (cd 07-frontend && ./node_modules/.bin/vite build && \
 *      PORT=4270 API_PROXY_TARGET=http://127.0.0.1:8070 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4270 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr070-c-settings-tell-the-truth.mjs
 *
 * ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** `sbh_dev` is reseeded
 * by other lanes, and a mid-run reseed looks exactly like a broken screen.
 *
 * ── WHAT IT ASSERTS (demo script C, clicked) ──────────────────────────────
 *   1  **THE WORK GROUP HOLDS SIX CARDS AND NONE OF THEM SAYS *arrives with
 *      Work*** — the sentence is absent from the DOM, not merely hidden. That
 *      sentence is the whole point of the wave: four cards carried it for three
 *      weeks.
 *   2  **A SKILL ADDED IS A SKILL LISTED** — *Backflow* is typed into the
 *      Skills card and comes back in the list, read off the DOM after the
 *      server's own answer.
 *   3  **A PRIORITY CARRIES ITS PROMISE** — *Urgent* shows *4 h*, the unit
 *      travelling with the number (hard rule 3).
 *   4  **NUMBERING SHOWS THE FOUR WORK SERIES**, `dispatch_batch` among them,
 *      and nothing in the product allocates from it (`BR-WRK-021`).
 *   5  **THE PARTS REGISTER DRAWS A PRICE AND NOT A COUNT**: `MTR-E1P` at
 *      `$96.00` on screen against `96.0000` on the wire (hard rule 2), and NO
 *      column headed ON HAND, REORDER AT or LOCATION, no reorder box, no
 *      in-cover pill — each asserted BY NAME.
 *   6  **THE SEGMENTED CONTROL HAS TWO SEGMENTS**, the second disabled with a
 *      reason, and the utilities compiled (computed style in a real engine).
 *      The Work strip carries FOUR tabs — wave B's *Awaiting approval* and
 *      wave C's *Parts* both survive — and none of the four unbuilt ones.
 *   7  **NO DATABASE ID AND NO INTERNAL REFERENCE REACHES A CLERK** (B14 rules
 *      31 and 32), and **NO SIDEWAYS SCROLL AT 1440**.
 *   8  **LONE STAR RIDGE SEES ITS OWN LISTS AND NONE OF BRAZOS BEND'S** — the
 *      wall, clicked rather than queried (hard rule 1; demo step 7).
 *   Screenshots land in `$SMOKE_OUT` (default /tmp/cr070-c-settings), beside
 *   which a reviewer opens `wireframes/Work-025.png`.

 * ⚠ **THE STRIP'S HANDLE CHANGED ON 2026-09-05 (`DEF-WRK-3955`).** Work drew its
 * own tab strip and tagged it `[data-work-tabs]` / `[data-work-tab="…"]`; that
 * strip is deleted and the strip is now the SHARED page header's, which carries
 * `[data-page-header-tabs]` and `[data-tab="…"]` on every module. The selectors
 * below moved with it. If a check here goes looking for `data-work-tab` again,
 * the module has grown a second strip and that is the defect, not the selector.
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4270";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const TENANT2 = process.env.SMOKE_TENANT2 ?? "";
const EMAIL2 = process.env.SMOKE_EMAIL2 ?? "";
const PASSWORD2 = process.env.SMOKE_PASSWORD2 ?? PASSWORD;
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr070-c-settings";
const VIEWPORT = { width: 1440, height: 1000 };

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

const SIDEWAYS =
  "Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)";

/** The six cards the Work group must hold, in `referenceDataConfig`'s order. */
const WORK_CARDS = [
  "Work order types",
  "Work priorities & SLA",
  "Skills catalog",
  "Safety kits",
  "Parts categories",
  "Parts register",
];

/** The head of Work-025 and its six columns, MINUS the three the card forbids. */
const PARTS_HEAD = {
  kicker: "Work",
  title: "Parts",
  sentence: "What your crews fit, and what each one costs.",
  columns: ["Part #", "Description", "Category", "Unit", "Unit cost", "Status"],
};

/**
 * ⚠ THE POINT OF THIS FILE. Each of these is drawn on `Work-025.png` and each
 * is forbidden by `BR-WRK-019` until `OQ-WRK-1490` is ruled. Asserted as column
 * headers AND as free text, because a lane could add either one alone.
 */
const FORBIDDEN_STOCK = ["On hand", "Reorder at", "Location", "In cover", "Below reorder"];

/** Anything a clerk must never be shown (B14 rules 31 and 32). */
const FORBIDDEN_IN_CLERK_COPY = [
  /\bBR-[A-Z]{3}-\d{3,5}\b/,
  /\bOQ-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /\bDEF-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /\bUS-[A-Z]{3}-\d{3,5}\b/,
  /\bWork-0\d\d\b/,
  /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
];

/** The sentence four of these cards carried for three weeks. */
const ARRIVES_WITH_WORK = "arrives with Work";

async function signIn(page, tenant, email, password) {
  await page.goto(`${BASE}/${tenant}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", email);
  await page.fill("#signin-password", password);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });
}

/** The Work group's own <section>, located by its heading rather than by index. */
function workGroup(page) {
  return page.locator("section.lookup-group").filter({ has: page.locator("h3", { hasText: /^Work$/ }) });
}

async function openReferenceData(page, tenant) {
  await page.goto(`${BASE}/${tenant}/settings/reference-data`, { waitUntil: "networkidle" });
  await page.waitForSelector("section.lookup-group", { timeout: 20000 });
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });

  // The server's own answers, captured rather than inferred.
  let servedParts = null;
  let servedSkills = null;
  page.on("response", async (response) => {
    const url = response.url();
    try {
      if (/\/work\/parts(?:\?|$)/.test(url)) servedParts = JSON.parse(await response.text());
      else if (/\/lookups\?.*work_skills/.test(url)) servedSkills = JSON.parse(await response.text());
    } catch {
      // a redirect or a non-JSON body has nothing to read
    }
  });

  console.log(`cr070-c: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);

  await signIn(page, TENANT, EMAIL, PASSWORD);
  console.log("   signed in as Alex Reed's stand-in (the owner login)");

  // ═════════════════════════════════════════════════════════════════════════
  // 1 · Settings → Configure → Reference data: six cards, and the grey
  //     sentence gone (demo steps 1–2)
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── the Work group: six cards, and the sentence that left ──");
  await openReferenceData(page, TENANT);
  await page.screenshot({ path: join(OUT, "reference-data-work-group.png"), fullPage: true });

  const group = workGroup(page);
  check((await group.count()) === 1, "the Work group is on the page");
  const cardNames = await group.locator("button.lookup-card span.n").allInnerTexts();
  const trimmed = cardNames.map((s) => s.trim());
  check(
    trimmed.length === 6,
    `the Work group holds ${trimmed.length} card(s) — expected 6: ${trimmed.join(" · ")}`,
  );
  for (const name of WORK_CARDS) {
    check(trimmed.includes(name), `the card "${name}" is there`);
  }

  // ⚠ THE WAVE'S WHOLE POINT — asserted over the WHOLE document, not the group,
  // because a stale copy of the sentence anywhere on this screen is the defect.
  const refText = await page.evaluate(() => document.body.innerText);
  check(
    !refText.includes(ARRIVES_WITH_WORK),
    `no card says "${ARRIVES_WITH_WORK}" any more`,
  );
  // The four that carried it must now carry a COUNT instead of an absence.
  // ⚠ MEASURED, not assumed. The first draft of this check looked for a state
  // of `present` and found none — the state a seeded list reports is `seeded`,
  // and the walkthrough was wrong rather than the screen. The counts below are
  // the SERVER's, rendered in the badge slot: five lists answering 8 · 4 · 8 ·
  // 4 · 4 is what "the card holds real rows" means, and it is the sentence the
  // whole wave is named for.
  const badges = await group.locator("button.lookup-card span.v").evaluateAll((nodes) =>
    nodes.map((n) => ({ text: n.textContent.trim(), state: n.getAttribute("data-card-state") })),
  );
  const counted = badges.filter((b) => b.state === "seeded").length;
  check(
    counted === 5,
    `${counted} of the six cards report a live count from the server: ${badges
      .map((b) => b.text)
      .join(" · ")}`,
  );
  // The sixth is a LINK to the register, not a lookup list — `GET /lookups`
  // never answers for it, so `absent` with no count is correct and a count
  // here would be the defect (referenceDataConfig's own note says so).
  check(
    badges[5].state === "absent",
    `the Parts register card is a link and reports no count (state ${badges[5].state})`,
  );
  // The five counts are the review-ledger row's own figures, on screen.
  check(
    badges
      .slice(0, 5)
      .map((b) => b.text.replace(/[^0-9]/g, ""))
      .join(",") === "8,4,8,4,4",
    `the five lists hold 8 · 4 · 8 · 4 · 4 rows — the figures the review row quotes`,
  );

  // 2 · add the skill *Backflow* (demo step 3)
  console.log("\n── add a skill, and see it listed ──");
  await group.locator("button.lookup-card", { hasText: "Skills catalog" }).click();
  // ⚠ The card opens the LIST; the form is behind *+ Add entry*. The first
  // draft waited on `#code` straight after the card click and timed out at
  // twenty seconds, which reads exactly like a broken screen and was the
  // walkthrough being wrong about its own product.
  await page.waitForSelector("tbody tr", { timeout: 20000 });
  await page.locator("button", { hasText: "+ Add entry" }).first().click();
  await page.waitForSelector("#code", { timeout: 20000 });
  await page.screenshot({ path: join(OUT, "skills-before.png"), fullPage: true });
  const beforeRows = await page.locator("tbody tr").count();
  await page.fill("#code", "BACKFLOW");
  await page.fill("#name", "Backflow");
  await page.locator('button[type="submit"]').first().click();
  await page
    .waitForFunction(
      () => document.body.innerText.includes("Backflow"),
      null,
      { timeout: 20000 },
    )
    .catch(() => {});
  const afterRows = await page.locator("tbody tr").count();
  const skillsText = await page.evaluate(() => document.body.innerText);
  check(skillsText.includes("Backflow"), "the skill Backflow is in the list after saving");
  check(
    afterRows === beforeRows + 1,
    `the list grew by one row (${beforeRows} → ${afterRows})`,
  );
  await page.screenshot({ path: join(OUT, "skills-after-backflow.png"), fullPage: true });

  // 3 · a priority carries its promise (demo step 4)
  console.log("\n── Urgent · 4 h ──");
  await openReferenceData(page, TENANT);
  await workGroup(page).locator("button.lookup-card", { hasText: "Work priorities & SLA" }).click();
  await page.waitForSelector("tbody tr", { timeout: 20000 });
  await page.screenshot({ path: join(OUT, "priorities.png"), fullPage: true });
  const urgent = page.locator("tbody tr", { hasText: "Urgent" }).first();
  check((await urgent.count()) >= 1, "the priority Urgent is listed");
  const urgentCells = (await urgent.locator("td").allInnerTexts()).map((s) => s.trim());
  check(
    urgentCells.some((c) => c === "4 h"),
    `Urgent shows its promise with the unit — read ${JSON.stringify(urgentCells)}`,
  );
  const prioritiesText = await page.evaluate(() => document.body.innerText);
  for (const [name, hours] of [["High", "8 h"], ["Normal", "72 h"], ["Low", "168 h"]]) {
    check(prioritiesText.includes(hours), `${name} shows ${hours}`);
  }

  // 4 · Numbering: the four Work series (demo step 5)
  console.log("\n── Numbering: the four Work series ──");
  await page.goto(`${BASE}/${TENANT}/settings/number-series`, { waitUntil: "networkidle" });
  await page.waitForSelector("tbody tr", { timeout: 20000 });
  await page.screenshot({ path: join(OUT, "numbering.png"), fullPage: true });
  const numberingText = await page.evaluate(() => document.body.innerText);
  for (const label of ["Connection", "Work order", "Service template", "Dispatch batch"]) {
    check(numberingText.includes(label), `the ${label} series is shown`);
  }

  // ═════════════════════════════════════════════════════════════════════════
  // 5 · Work → Parts: a price, and NOT a count (demo step 6)
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── Work → Parts, against wireframes/Work-025.png ──");
  await page.goto(`${BASE}/${TENANT}/work/parts`, { waitUntil: "networkidle" });
  await page.waitForFunction(
    () =>
      document.querySelector('[data-work-parts=""] tbody tr') !== null ||
      document.body.innerText.includes("No parts yet"),
    null,
    { timeout: 20000 },
  );
  await page.screenshot({ path: join(OUT, "work-parts.png"), fullPage: true });
  const partsText = await page.evaluate(() => document.body.innerText);

  // the head, against the pack
  const kicker = ((await page.locator('[data-work-parts=""] [data-kicker]').first().innerText()) ?? "").trim();
  check(kicker.toLowerCase() === PARTS_HEAD.kicker.toLowerCase(), `kicker reads "${kicker}"`);
  const title = ((await page.locator('[data-work-parts=""] h1').first().innerText()) ?? "").trim();
  check(title === PARTS_HEAD.title, `title reads "${title}"`);
  check(partsText.includes(PARTS_HEAD.sentence), "the one sentence under the title is this screen's");

  const headers = await page.locator('[data-work-parts=""] thead th').allInnerTexts();
  const cleaned = headers.map((h) => h.replace(/[⇅↑↓]/g, "").trim()).filter((h) => h !== "");
  check(
    cleaned.length === 6,
    `the register draws ${cleaned.length} column(s): ${cleaned.join(" · ")}`,
  );
  check(
    PARTS_HEAD.columns.every((c, i) => (cleaned[i] ?? "").toLowerCase() === c.toLowerCase()),
    `columns in the pack's order: ${cleaned.join(" · ")}`,
  );

  // ⚠ THE ABSENCES — the reason this walkthrough exists. By name, twice over.
  for (const forbidden of FORBIDDEN_STOCK) {
    const inHeaders = cleaned.some((h) => h.toLowerCase() === forbidden.toLowerCase());
    check(!inHeaders, `no column headed ${forbidden.toUpperCase()}`);
    check(
      !new RegExp(forbidden.replace(/ /g, "\\s+"), "i").test(partsText),
      `the words "${forbidden}" appear nowhere on the register`,
    );
  }
  check(
    !/Reorder\s*—|parts at or below|units needed to restore/i.test(partsText),
    "no reorder banner (the drawing's, forbidden by the card)",
  );

  // hard rule 2 — four decimals stored, two displayed
  const rowE1P = page.locator('[data-work-parts=""] tbody tr', { hasText: "MTR-E1P" });
  if ((await rowE1P.count()) >= 1) {
    const cells = (await rowE1P.first().locator("td").allInnerTexts()).map((s) => s.trim());
    check(cells.includes("$96.00"), `MTR-E1P shows $96.00 — read ${JSON.stringify(cells)}`);
    if (servedParts !== null) {
      const served = servedParts.results.find((r) => r.part_no === "MTR-E1P");
      check(
        served !== undefined && served.unit_cost === "96.0000",
        `and the server sent ${served === undefined ? "nothing" : `"${served.unit_cost}"`} — four decimals stored, two displayed`,
      );
    } else {
      check(false, "GET /work/parts was never observed — the table may be drawing from React");
    }
  } else {
    check(false, "MTR-E1P is not in the register — was the fixture loaded?");
  }

  // ⚠ AND THE SERVER MUST NOT PUBLISH THE KEYS EITHER (US-WRK-010 TC-5). A
  // screen that merely declines to DRAW a stock column, over a payload that
  // carries one, is one line of JSX away from the thing the rule forbids.
  if (servedParts !== null && servedParts.results.length > 0) {
    const keys = Object.keys(servedParts.results[0]);
    for (const key of ["on_hand", "reorder_at", "location"]) {
      check(!keys.includes(key), `GET /work/parts publishes no "${key}" key`);
    }
  }

  // 6 · the segmented control, and proof the utilities compiled
  console.log("\n── the segmented control ──");
  const segments = await page.locator("[data-segment]").evaluateAll((nodes) =>
    nodes.map((n) => ({
      id: n.getAttribute("data-segment"),
      text: n.textContent.trim(),
      disabled: n.hasAttribute("disabled") || n.getAttribute("aria-disabled") === "true",
    })),
  );
  check(segments.length === 2, `the control has ${segments.length} segment(s) — expected 2`);
  if (segments.length === 2) {
    check(!segments[0].disabled, `the first segment (${segments[0].text}) is live`);
    check(segments[1].disabled, `the second segment (${segments[1].text}) is disabled`);
    check(
      /arrives with parts on jobs/i.test(partsText),
      "and it says WHY, in words, rather than being silently dead",
    );
  }
  const controlPainted = await page
    .locator("[data-segmented-control]")
    .first()
    .evaluate((el) => {
      const s = getComputedStyle(el);
      return { display: s.display, gap: s.gap };
    })
    .catch(() => null);
  if (controlPainted !== null) {
    check(
      controlPainted.display === "flex" || controlPainted.display === "inline-flex",
      `the control painted (display ${controlPainted.display})`,
    );
  }

  // ⚠ THE STRIP CARRIES BOTH WAVES' TABS, AND THAT IS THE CHECK. `WorkShell.tsx`
  // says in its own header that two lanes edit `WORK_TABS` in the same hour and
  // whichever commits second must re-derive or a tab disappears. Wave B adds
  // *Awaiting approval* and wave C adds *Parts*; this walkthrough was written
  // when the strip read `orders,parts,templates` and correctly went RED the
  // moment wave B landed its tab, which is the guard working rather than
  // failing. Four tabs of the inventory's eight have a screen at this wave;
  // the other four are asserted ABSENT so a lane cannot half-draw one (law 2).
  const tabs = await page.locator("[data-page-header-tabs] [data-tab]").evaluateAll((nodes) =>
    nodes.map((n) => n.getAttribute("data-tab")),
  );
  check(
    tabs.join(",") === "orders,approvals,parts,templates",
    `the strip has the four tabs whose screen exists (${tabs.join(", ")})`,
  );
  for (const unbuilt of ["crews", "map", "rules", "performance"]) {
    check(!tabs.includes(unbuilt), `no tab for ${unbuilt} — its screen does not exist yet`);
  }

  // 7 · nothing internal reaches the clerk, and no sideways scroll
  console.log("\n── the clerk's eye ──");
  for (const pattern of FORBIDDEN_IN_CLERK_COPY) {
    const hit = partsText.match(pattern);
    check(hit === null, `no ${pattern} in clerk copy${hit ? ` — found ${hit[0]}` : ""}`);
  }
  const sideways = await page.evaluate(SIDEWAYS);
  check(sideways === 0, `no sideways scroll at ${VIEWPORT.width} (overflow ${sideways}px)`);

  // ═════════════════════════════════════════════════════════════════════════
  // 8 · the wall, clicked — Lone Star Ridge sees none of it (demo step 7)
  // ═════════════════════════════════════════════════════════════════════════
  if (TENANT2 !== "" && EMAIL2 !== "") {
    console.log(`\n── ${TENANT2}: its own lists, none of Brazos Bend's ──`);
    const page2 = await (await browser.newContext({ viewport: VIEWPORT })).newPage();
    let servedParts2 = null;
    page2.on("response", async (response) => {
      if (!/\/work\/parts(?:\?|$)/.test(response.url())) return;
      try {
        servedParts2 = JSON.parse(await response.text());
      } catch {
        // nothing to read
      }
    });
    await signIn(page2, TENANT2, EMAIL2, PASSWORD2);
    await page2.goto(`${BASE}/${TENANT2}/work/parts`, { waitUntil: "networkidle" });
    await page2
      .waitForFunction(
        () =>
          document.querySelector('[data-work-parts=""] tbody tr') !== null ||
          document.body.innerText.includes("No parts yet"),
        null,
        { timeout: 20000 },
      )
      .catch(() => {});
    await page2.screenshot({ path: join(OUT, "second-tenant-parts.png"), fullPage: true });
    const text2 = await page2.evaluate(() => document.body.innerText);
    check(!text2.includes("MTR-E1P"), "the second tenant sees none of Brazos Bend's parts");
    check(
      servedParts2 === null || servedParts2.count === 0,
      `the server served ${servedParts2 === null ? "nothing" : servedParts2.count} part(s) to the second tenant`,
    );
    await page2.goto(`${BASE}/${TENANT2}/settings/reference-data`, { waitUntil: "networkidle" });
    await page2.waitForSelector("section.lookup-group", { timeout: 20000 });
    await page2.screenshot({ path: join(OUT, "second-tenant-reference-data.png"), fullPage: true });
    const group2 = workGroup(page2);
    const cards2 = await group2.locator("button.lookup-card span.n").count();
    check(cards2 === 6, `and still sees all six cards (${cards2}) — the screen is the product's, the rows are the utility's`);
  } else {
    console.log(
      "\n   · second tenant not provisioned for this run (SMOKE_TENANT2 unset) — the wall is proved on PostgreSQL by tests/test_us_wrk_rls_pg.py, six cases under a non-superuser probe role",
    );
  }

  await browser.close();

  console.log(`\nscreenshots: ${OUT}`);
  if (failures.length > 0) {
    console.log(`\n⛔ ${failures.length} failure(s)`);
    for (const f of failures) console.log(`   · ${f}`);
    process.exit(1);
  }
  console.log("\n✓ cr070 wave C: Settings tells the truth, and the register counts nothing");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
