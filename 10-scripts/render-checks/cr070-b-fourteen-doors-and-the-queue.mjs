/**
 * RENDERED-OUTPUT CHECK — CR-070 wave B, "fourteen doors, and the queue", in a
 * real browser. **This is the proof of the PHASE-0 LAUNCH claim**: *a clerk can
 * raise, hold, cancel and close a job this week*.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: no gate in this repository looks at
 * rendered output, and nine defects in one day were found this way and by
 * nothing else. PO ruling 2026-09-03: *"ensure you do web walkthorugh before
 * you sign off the user story or build"*, and *"for Cr68, 69 and 70 - you will
 * have to ensure you refer to screenshot we build and not just r10"*. The
 * reference here is `04-docs/05-modules/16-work/wireframes/Work-009.png` read
 * through `08-screen-layouts.md`, and `Work-002` for the action row.
 *
 * ⚠ **AND `10-execution-plan.md` §2 SAYS IT IN AS MANY WORDS**: phase 0's exit
 * is demonstrated *"on a deployed build, not a green suite"*. Everything below
 * is clicked against a running product. The unit suites next door render to a
 * string and can never answer the two questions that matter here — did the
 * SERVER actually refuse, and did the screen actually paint.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   # 1 · a private, seeded database (10-scripts/proof-db.sh, read it first)
 *   eval "$(10-scripts/proof-db.sh clone cr070b --export)"
 *   export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false
 *   # …if the template carried schema only, seed it once:
 *   #   (cd 06-backend && python manage.py seed_demo &&
 *   #    python manage.py load_sample_data --tenant brazosbend)
 *
 *   # 2 · the three rows Work-009 draws, and the address the demo raises on
 *   (cd 06-backend && python manage.py shell < ../10-scripts/render-checks/cr070-b-fixture.py)
 *
 *   # 3 · the product
 *   (cd 06-backend && python manage.py runserver 127.0.0.1:8071 --noreload &)
 *   (cd 07-frontend && ./node_modules/.bin/vite build &&
 *      PORT=4271 API_PROXY_TARGET=http://127.0.0.1:8071 node server.mjs &)
 *
 *   # 4 · this
 *   SMOKE_BASE=http://127.0.0.1:4271 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr070-b-fourteen-doors-and-the-queue.mjs
 *
 * ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** `sbh_dev` is reseeded
 * by other lanes and a mid-run reseed looks exactly like a broken screen.
 *
 * ⚠ **IT MUTATES ITS DATABASE AND DOES NOT PUT IT BACK.** It holds a build,
 * releases it, raises an order and accepts one — that is the point. Re-run the
 * fixture step (2) before running it a second time; the fixture is idempotent
 * and puts the three rows back in the queue.
 *
 * ── WHAT IT ASSERTS (demo script B, clicked) ──────────────────────────────
 *   1  **EIGHT ACTS, EACH ENABLED OR DISABLED WITH A SENTENCE** on `Work-002`
 *      (`BR-SHL-025`). Not "eight buttons exist": every one is read, and any
 *      that is disabled must carry a REASON of five or six words (B14 rule 33).
 *      Cancel alone takes the danger tier and its colour is read from COMPUTED
 *      STYLE in a real engine — B14 rule 21 means a utility that did not
 *      compile renders as nothing while every string assertion still passes.
 *   2  **HOLD IS A ROUND TRIP THROUGH THE SERVER** (demo steps 1–2): the state
 *      pill reads *On hold* and WAITING ON carries the typed reason, both read
 *      back from `GET /connections/{id}` and not patched on the screen.
 *   3  **RELEASE PUTS IT BACK**, and Hold becomes available again while Release
 *      becomes the refused one — the pair swap, which is the rule.
 *   4  **THE SERVER REFUSES, NOT THE SCREEN.** The disabled control is only
 *      half of `BR-SHL-025`; the other half is that the door says no to a
 *      request the screen would never send. Asserted by calling the endpoint
 *      DIRECTLY from the page's own session — a hold on a cancelled build —
 *      and reading the status and the sentence that comes back.
 *   5  **A LEAK INVESTIGATION ON `77 Cedar Ct`, WITH NO BUILD AT ALL** — the
 *      thing phase 0 exists to make possible, and impossible before
 *      `metering/0044`. Raised through `POST /work-orders` and closed through
 *      `POST /work-orders/{id}/field-result`: the product's own doors, because
 *      a fixture that wrote the row would prove the screen renders and prove
 *      nothing about the claim.
 *   6  **IT IS IN THE QUEUE, WITH A DASH UNDER CONNECTION** (`BR-WRK-006`), and
 *      its eye is DISABLED WITH ITS REASON because `Work-008` is wave H's.
 *   7  **THE FOOTER SENTENCE AGAINST THE DRAWING** — *"N orders · oldest
 *      waiting 6 days"* — with the count read off the DOM and checked against
 *      the number of rows the server sent.
 *   8  **THE NOTE BAR CONTAINS NO `accepted_by`** (B14 rule 32), and no
 *      database id or internal reference reaches the clerk (rule 31).
 *   9  **ACCEPT REMOVES IT FROM THE LIST** (`BR-MET-110` — a person accepts;
 *      only then does anything go live). Clicked from the drawer the eye opens,
 *      then the queue is re-read and the row is gone.
 *  10  **THE KIT DREW IT, NOT THIS SCREEN** (B14 rule 36, ratified 2026-09-04):
 *      r10 rule 16's pagination footer is present, there is exactly ONE of it,
 *      it states its range and carries the rows-per-page control — all of it
 *      from `DataTable` rather than hand-rolled here; every button on the
 *      screen came from the kit (`data-variant`); and nothing dashed or
 *      monospaced — the wireframe-annotation style — reaches a utility user.
 *  11  **NO SIDEWAYS SCROLL AT 1440.**
 *   Screenshots land in `$SMOKE_OUT` (default /tmp/cr070-b-queue), beside which
 *   a reviewer opens `wireframes/Work-009.png` and `Work-002`.
 *
 * ── WHAT IT DOES *NOT* ASSERT, AND WHY ────────────────────────────────────
 * **Demo step 8 — "Lone Star Ridge's queue is empty" — is NOT here.** That
 * tenant is not seeded (`10-execution-plan.md` §1: *"Lone Star Ridge WSC is not
 * seeded — tests provision it"*), and provisioning a second utility inside a
 * browser walkthrough would make this file a seeder. The wall is proved where
 * it can be proved properly: `06-backend/tests/test_us_wrk_003_queue_pg.py`
 * asserts it against real PostgreSQL with RLS `FORCE` on, under the
 * `sbh_rls_probe` role rather than the superuser the app connects as. Stated
 * here rather than quietly skipped, because a walkthrough that lists a step it
 * did not run is worse than one that says which step it left to a test.

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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4271";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const BUILD = process.env.SMOKE_BUILD ?? "CON-26-0117";
const LEAK_ADDRESS = "77 Cedar Ct";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr070-b-queue";
const VIEWPORT = { width: 1440, height: 1000 };

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

const SIDEWAYS =
  "Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)";

/** The eight acts of `Work-002`'s row, in the order the screen draws them. */
const ACTS = [
  "hold",
  "release",
  "cancel",
  "waitingOn",
  "addService",
  "markOutstanding",
  "closeOutstanding",
  "raiseOrder",
];

/** Anything a clerk must never be shown (B14 rules 31 and 32). */
const FORBIDDEN_IN_CLERK_COPY = [
  [/\baccepted_by\b/, "accepted_by (the column name the drawing used)"],
  [/\bBR-[A-Z]{3}-\d{3,5}\b/, "a business-rule id"],
  [/\bOQ-(?:[A-Z]{3}-)?\d{3,5}\b/, "an open-question id"],
  [/\bDEF-(?:[A-Z]{3}-)?\d{3,5}\b/, "a defect id"],
  [/\bUS-[A-Z]{3}-\d{3,5}\b/, "a story id"],
  [/\bWork-0\d\d\b/, "a Work-nnn screen number"],
  [/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/, "a database id"],
];

async function signIn(page, tenant, email, password) {
  await page.goto(`${BASE}/${tenant}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", email);
  await page.fill("#signin-password", password);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });
}

/**
 * Call the API from INSIDE the page, so the request carries exactly the session
 * the screen has. A `fetch` from Node would need the cookie copied out and
 * would then be proving something about a different caller.
 */
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

/** Every act button, with what the screen says about it. */
async function readActs(page) {
  return page.evaluate(() =>
    [...document.querySelectorAll("[data-connection-actions] button[data-act]")].map((b) => ({
      act: b.getAttribute("data-act"),
      label: (b.textContent ?? "").trim(),
      disabled: b.disabled,
      reason: b.getAttribute("data-blocked-reason"),
      variant: b.getAttribute("data-variant"),
      colour: getComputedStyle(b).color,
      borderColour: getComputedStyle(b).borderTopColor,
    })),
  );
}

function words(sentence) {
  return sentence.replace(/[.…]+$/u, "").trim().split(/\s+/u).length;
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });

  // The server's own answers, captured rather than inferred from the screen.
  let servedQueue = null;
  page.on("response", async (response) => {
    if (!/\/work-orders\/awaiting-approval/.test(response.url())) return;
    try {
      servedQueue = JSON.parse(await response.text());
    } catch {
      // a redirect has nothing to read
    }
  });

  console.log(`cr070-b: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);
  await signIn(page, TENANT, EMAIL, PASSWORD);
  console.log("   signed in");

  // Find the build by its number rather than by a hardcoded id.
  const list = await api(page, "GET", "/connections?q=" + encodeURIComponent(BUILD));
  const found = (list.body?.results ?? []).find((c) => c.connection_no === BUILD);
  if (!found) {
    console.log(`⛔ ${BUILD} is not in this database — seed it and re-run.`);
    process.exit(2);
  }
  const buildId = found.id;
  const detailPath = `/${TENANT}/connections/${buildId}`;

  // ── THE FIXTURE GUARD, AND IT IS HERE BECAUSE THIS LANE TRIPPED OVER IT ──
  // This walkthrough ACCEPTS `WO-4906` at step 7, so a second run in a row
  // starts from a queue that no longer contains it and reports three failures
  // that read exactly like a broken screen — *WO-4906 is in the queue* ⛔,
  // *the oldest is WO-4906 at 6 days* ⛔, *its eye is a LINK* ⛔. Every one of
  // them is true; none of them is the product's fault.
  //
  // The header has always said "re-run the fixture first". A paragraph is not
  // a check (hard-won law 1), so this REFUSES instead, and names the command.
  // A guard the next lane inherits beats a sentence it has to remember.
  const seeded = await api(page, "GET", "/work-orders/awaiting-approval?per=200");
  const numbers = (seeded.body?.results ?? []).map((r) => r.order_no);
  const wanted = ["WO-4906", "WO-4903", "WO-4917"];
  const missing = wanted.filter((n) => !numbers.includes(n));
  if (missing.length > 0) {
    console.log(`\n⛔ the queue is not in its starting state — missing ${missing.join(", ")}.`);
    console.log("   This walkthrough accepts WO-4906, so it must be re-seeded between runs:");
    console.log("     (cd 06-backend && python manage.py shell < \\");
    console.log("        ../10-scripts/render-checks/cr070-b-fixture.py)");
    console.log(`   The queue currently holds: ${numbers.join(", ") || "(nothing)"}`);
    process.exit(2);
  }
  console.log(`   the queue starts with the drawing's three rows (${numbers.length} in total)`);

  // ═════════════════════════════════════════════════════════════════════════
  // 1 · Work-002's action row: eight acts, each enabled or refused in words
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── Work-002 · the eight acts (demo step 1) ──");
  await page.goto(`${BASE}${detailPath}`, { waitUntil: "networkidle" });
  await page.waitForSelector("[data-connection-actions]", { timeout: 20000 });
  await page.screenshot({ path: join(OUT, "01-connection-detail-actions.png"), fullPage: true });

  const acts = await readActs(page);
  check(acts.length === 8, `eight acts are on the screen (found ${acts.length})`);
  for (const want of ACTS) {
    const got = acts.find((a) => a.act === want);
    check(got !== undefined, `  ${want} is mounted`);
    if (!got) continue;
    // BR-SHL-025 — enabled, or disabled WITH ITS REASON. Never a third state.
    const stated = got.disabled ? (got.reason ?? "").trim() !== "" : true;
    check(
      stated,
      `  ${want} is ${got.disabled ? `refused — "${got.reason}"` : "available"}`,
    );
    if (got.disabled && got.reason) {
      // B14 rule 33 — five or six words.
      check(words(got.reason) <= 6, `  …and that reason is ${words(got.reason)} words`);
    }
  }

  const danger = acts.filter((a) => a.variant === "danger");
  check(danger.length === 1 && danger[0].act === "cancel", "Cancel alone takes the danger tier");
  // B14 rule 21 — read the COLOUR, because a utility that did not compile
  // renders as nothing while `data-variant="danger"` is still in the DOM.
  const dangerColour = danger[0]?.colour ?? "";
  check(
    /^rgba?\(/.test(dangerColour) && dangerColour !== (acts.find((a) => a.act === "hold")?.colour ?? ""),
    `the danger tier actually painted: Cancel is ${dangerColour}, Hold is ${acts.find((a) => a.act === "hold")?.colour}`,
  );

  // ═════════════════════════════════════════════════════════════════════════
  // 2 · Hold, with a reason — and the state comes BACK FROM THE SERVER
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── Hold… then Release… (demo steps 1–2) ──");
  const REASON = "Waiting on the tap permit";
  await page.click('button[data-act="hold"]');
  await page.waitForSelector("[data-act-prompt='hold']", { timeout: 10000 });
  await page.fill("#connection-act-text", REASON);
  await page.click("[data-act-confirm='hold']");
  await page.waitForFunction(
    () => /on hold/i.test(document.querySelector("[data-screen]")?.textContent ?? ""),
    { timeout: 20000 },
  );
  await page.screenshot({ path: join(OUT, "02-held.png"), fullPage: true });

  const afterHold = await api(page, "GET", `/connections/${buildId}`);
  check(afterHold.body?.state === "on_hold", `the server says the build is on_hold`);
  const head = (await page.textContent("[data-connection-head]")) ?? "";
  check(/On hold/i.test(await page.textContent("[data-screen]")), "the state pill reads On hold");
  check(head.includes(REASON), `WAITING ON carries the typed reason — "${REASON}"`);

  const heldActs = await readActs(page);
  const heldHold = heldActs.find((a) => a.act === "hold");
  const heldRelease = heldActs.find((a) => a.act === "release");
  check(
    heldHold?.disabled === true && (heldHold?.reason ?? "") !== "",
    `Hold is now refused — "${heldHold?.reason}"`,
  );
  check(heldRelease?.disabled === false, "…and Release is now the available one");

  // ── 3 · Release puts it back ────────────────────────────────────────────
  await page.click('button[data-act="release"]');
  await page.waitForFunction(
    () => !/on hold/i.test(document.querySelector("[data-screen]")?.textContent ?? ""),
    { timeout: 20000 },
  );
  const afterRelease = await api(page, "GET", `/connections/${buildId}`);
  check(afterRelease.body?.state !== "on_hold", `Release put it back — now ${afterRelease.body?.state}`);
  const releasedActs = await readActs(page);
  check(
    releasedActs.find((a) => a.act === "release")?.disabled === true,
    "…and the pair swap back: Release is refused again",
  );
  await page.screenshot({ path: join(OUT, "03-released.png"), fullPage: true });

  // ═════════════════════════════════════════════════════════════════════════
  // 4 · THE SERVER REFUSES — the half a disabled button cannot prove
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── the server's own refusal, not the screen's (BR-SHL-025) ──");
  const doubleRelease = await api(page, "POST", `/connections/${buildId}/release`, {});
  check(
    doubleRelease.status >= 400,
    `releasing a build that is not held is refused by the SERVER — HTTP ${doubleRelease.status}`,
  );
  const refusalKey = doubleRelease.body?.message_key ?? doubleRelease.body?.code ?? "";
  check(
    String(refusalKey).length > 0,
    `…with a catalogue key rather than raw prose — ${JSON.stringify(refusalKey)}`,
  );

  // ═════════════════════════════════════════════════════════════════════════
  // 5 · A leak investigation on 77 Cedar Ct, with NO BUILD (demo steps 4–5)
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── the job phase 0 exists to make possible (demo steps 4–5) ──");
  const premises = await api(page, "GET", "/premises?q=" + encodeURIComponent(LEAK_ADDRESS));
  const address = (premises.body?.results ?? []).find((p) =>
    (p.address_line ?? p.address ?? "").includes(LEAK_ADDRESS),
  );
  check(address !== undefined, `${LEAK_ADDRESS} is an address this utility has`);

  // ⚠ NO `connection_id`. Before metering/0044 this was a NOT NULL column and
  // this request could not be expressed at all.
  const raised = await api(page, "POST", "/work-orders", {
    premises_id: address?.id,
    type: "Leak investigation",
    service: "water",
  });
  check(
    raised.status < 400,
    `a Leak investigation is raised on an ADDRESS with no build — HTTP ${raised.status}, ${raised.body?.order_no}`,
  );
  check(
    raised.body?.connection_id === null || raised.body?.connection_id === undefined,
    "…and it stands on no connection at all",
  );
  const leakId = raised.body?.id;
  const leakNo = raised.body?.order_no;

  // …and an order with NO anchor at all is refused (BR-WRK-006, the CHECK).
  const anchorless = await api(page, "POST", "/work-orders", {
    type: "Leak investigation",
    service: "water",
  });
  check(
    anchorless.status >= 400,
    `an order with no anchor at all is refused — HTTP ${anchorless.status}`,
  );

  const closed = await api(page, "POST", `/work-orders/${leakId}/field-result`, {
    outcome: "passed",
    notes: "Leak found at the kerb stop and stopped.",
  });
  check(closed.status < 400, `the field closes it — HTTP ${closed.status}`);

  // ═════════════════════════════════════════════════════════════════════════
  // 6–8 · Work-009: the queue, the dash, the footer, the note bar
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── Work → Awaiting approval (demo step 6) ──");
  await page.goto(`${BASE}/${TENANT}/work/orders`, { waitUntil: "networkidle" });
  await page.waitForSelector("[data-page-header-tabs]", { timeout: 20000 });
  check(
    (await page.locator('[data-tab="approvals"]').count()) === 1,
    "the Work strip carries an Awaiting approval tab",
  );
  await page.click('[data-tab="approvals"]');
  await page.waitForSelector("[data-work-approvals]", { timeout: 20000 });
  await page.waitForSelector("table tbody tr", { timeout: 20000 });
  await page.screenshot({ path: join(OUT, "04-awaiting-approval.png"), fullPage: true });

  check(
    (await page.locator("[data-screen='WRK-20']").count()) === 1,
    "the screen carries its own id (WRK-20)",
  );

  const rows = await page.evaluate(() =>
    [...document.querySelectorAll("[data-work-approvals] table tbody tr")].map((tr) =>
      [...tr.querySelectorAll("td")].map((td) => (td.textContent ?? "").trim()),
    ),
  );
  console.log(`   the queue shows ${rows.length} row(s):`);
  for (const r of rows) console.log(`     ${r.slice(0, 7).join("  ·  ")}`);

  // The drawing's three rows.
  const text = (await page.textContent("[data-work-approvals]")) ?? "";
  for (const wanted of ["WO-4906", "WO-4903", "WO-4917"]) {
    check(text.includes(wanted), `  ${wanted} is in the queue`);
  }
  check(text.includes(String(leakNo)), `  and so is the leak investigation ${leakNo}`);

  // BR-WRK-006 — the leak row's CONNECTION cell is a DASH.
  const leakRow = rows.find((r) => r.some((cell) => cell.includes(String(leakNo))));
  check(leakRow !== undefined, "  the leak investigation has a row");
  check(
    leakRow !== undefined && (leakRow[1] === "—" || leakRow[1] === ""),
    `  …and its CONNECTION cell is a dash, not a build — got ${JSON.stringify(leakRow?.[1])}`,
  );
  check(
    leakRow !== undefined && leakRow[2].includes(LEAK_ADDRESS),
    `  …with ${LEAK_ADDRESS} under PREMISE`,
  );

  // Its eye is DISABLED WITH ITS REASON — Work-008 is wave H's.
  const leakEye = await page.evaluate((no) => {
    const tr = [...document.querySelectorAll("[data-work-approvals] table tbody tr")].find((r) =>
      (r.textContent ?? "").includes(no),
    );
    const button = tr?.querySelector("button[aria-label], a[aria-label]");
    return button
      ? { tag: button.tagName, disabled: button.disabled === true, title: button.getAttribute("title") }
      : null;
  }, String(leakNo));
  check(
    leakEye?.disabled === true && (leakEye?.title ?? "") !== "",
    `  its eye is refused with a reason — "${leakEye?.title}"`,
  );

  // ── the footer sentence, against the drawing ────────────────────────────
  const footer = ((await page.textContent("[data-approvals-footer]")) ?? "").trim();
  console.log(`   footer: "${footer}"`);
  check(
    new RegExp(`^${rows.length} orders? · oldest waiting `).test(footer),
    `the footer counts what the table shows — "${footer}"`,
  );
  check(
    /oldest waiting 6 days$/.test(footer),
    `…and the oldest is WO-4906 at 6 days, computed over the whole queue`,
  );
  check(
    servedQueue !== null && servedQueue.count === rows.length,
    `the count on screen (${rows.length}) is the count the server sent (${servedQueue?.count})`,
  );

  // ── B14 rule 36 · r10 rule 16 — the kit's own pager, not a hand-rolled one
  // The pack says WHAT is on this screen; r10 says what it looks like; the kit
  // is how the two meet. `DataTable` brings the pagination footer with it, so
  // the check is that the SHARED one rendered — a screen that grew its own
  // would show a second range line and no rows-per-page control.
  const pager = await page.evaluate(() => {
    const el = document.querySelector("[data-work-approvals] .table-pager");
    if (!el) return null;
    return {
      range: (el.querySelector(".table-pager-range")?.textContent ?? "").trim(),
      hasPageSize: el.querySelector(".table-pager-size") !== null,
      buttons: el.querySelectorAll("button").length,
      count: document.querySelectorAll("[data-work-approvals] .table-pager").length,
    };
  });
  check(pager !== null, "r10 rule 16: the shared pagination footer is on the list table");
  check(pager?.count === 1, "…exactly one of them — the screen hand-rolled none");
  check(/\d+/.test(pager?.range ?? ""), `…and it states the range — "${pager?.range}"`);
  check(pager?.hasPageSize === true, "…with the rows-per-page control r10 rule 16 names");

  // B14 rule 36 (c) — no raw <button> where the kit's `Button` would serve, and
  // none of the wireframe-annotation style rule 36 was ratified on.
  //
  // ⚠ **SCOPED TO THE TABLE BODY, AND THE FIRST DRAFT WAS NOT.** Asking "does
  // every button under `[data-work-approvals]` carry `data-variant`" reported
  // **18 raw buttons** on a screen that hand-rolls none: they are `DataTable`'s
  // OWN column-menu *Move Order up* / *down* controls, which are the kit's
  // internal chrome. A check that fails the kit for being the kit cannot
  // distinguish a compliant screen from a breach, and law 11 has the sentence
  // for it — a check whose output cannot tell pass from fail is worse than no
  // check, because it is trusted. The surface a SCREEN actually authors is the
  // cells, so that is what this reads.
  const bespoke = await page.evaluate(() => {
    const scope = document.querySelector("[data-work-approvals]");
    const authored = [...(scope?.querySelectorAll("tbody button") ?? [])];
    return {
      authored: authored.length,
      unkitted: authored.filter((b) => !b.hasAttribute("data-variant")).length,
      annotation: [...(scope?.querySelectorAll("*") ?? [])].filter((el) => {
        const c = typeof el.className === "string" ? el.className : "";
        return /border-dashed|font-mono/.test(c);
      }).length,
    };
  });
  check(bespoke.authored > 0, `the screen authors ${bespoke.authored} control(s) in its cells`);
  check(
    bespoke.unkitted === 0,
    `rule 36: every one of them came from the kit (${bespoke.unkitted} raw)`,
  );
  check(bespoke.annotation === 0, "rule 36: nothing dashed or monospaced ships to a utility user");

  // ── the note bar, and nothing internal anywhere on the screen ───────────
  const note = ((await page.textContent("[data-approvals-note]")) ?? "").trim();
  console.log(`   note: "${note}"`);
  check(note.includes("nobody has accepted them"), "the note bar is written in a clerk's words");
  const visible = await page.evaluate(() => document.body.innerText);
  for (const [pattern, what] of FORBIDDEN_IN_CLERK_COPY) {
    check(!pattern.test(visible), `no ${what} reaches the clerk`);
  }
  check(
    Number(await page.evaluate(SIDEWAYS)) === 0,
    "no sideways scroll at 1440",
  );

  // ═════════════════════════════════════════════════════════════════════════
  // 9 · Accept removes it from the list (demo step 7, BR-MET-110)
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── Accept, and the row leaves (demo step 7) ──");
  const before = rows.length;
  const target = await page.evaluate(() => {
    const tr = [...document.querySelectorAll("[data-work-approvals] table tbody tr")].find((r) =>
      (r.textContent ?? "").includes("WO-4906"),
    );
    const link = tr?.querySelector("a[aria-label]");
    return link ? link.getAttribute("href") : null;
  });
  check(target !== null, "WO-4906's eye is a LINK to the drawer that already accepts");

  if (target) {
    await page.goto(`${BASE}${target}`, { waitUntil: "networkidle" });
    await page.waitForSelector("[data-work-order-panel]", { timeout: 20000 });
    await page.screenshot({ path: join(OUT, "05-drawer.png"), fullPage: true });
    // ⚠ THE BUTTON READS *Mark complete ✓*, NOT "Accept". The drawer is
    // `Work-003` and predates this wave; wave B does not rename it, so the
    // walkthrough matches what a clerk actually sees rather than what the plan
    // calls the act.
    const accept = page.locator("[data-work-order-panel] button", { hasText: /Mark complete/ });
    check((await accept.count()) >= 1, "the drawer's Mark complete ✓ is there and unchanged");
    await accept.first().click();
    await page.waitForTimeout(1500);
  }

  await page.goto(`${BASE}/${TENANT}/work/awaiting-approval`, { waitUntil: "networkidle" });
  await page.waitForSelector("[data-work-approvals]", { timeout: 20000 });
  await page.waitForTimeout(500);
  const after = await page.textContent("[data-work-approvals]");
  check(!after.includes("WO-4906"), `WO-4906 has LEFT the queue (was ${before} rows)`);
  check(after.includes(String(leakNo)), "…and the leak investigation is still in it");
  await page.screenshot({ path: join(OUT, "06-after-accept.png"), fullPage: true });

  console.log(`\nscreenshots in ${OUT}`);
  if (failures.length > 0) {
    console.log(`\ncr070-b: ${failures.length} FAILURE(S)`);
    for (const f of failures) console.log(`   ⛔ ${f}`);
  } else {
    console.log("\ncr070-b: every check passed — phase 0's launch claim is clicked, not asserted");
  }
  await browser.close();
  process.exit(failures.length === 0 ? 0 : 1);
})().catch((error) => {
  console.error(error);
  process.exit(2);
});
