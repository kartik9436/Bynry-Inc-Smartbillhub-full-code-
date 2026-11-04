// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-044 (offline capture and one sync) · US-WRK-045 (the close
//           from the phone) · US-WRK-046 (the reading that posts) ·
//           US-WRK-035 (the letter, refused)
//           Screens: Work-010, Work-011, Work-012, Work-009
// Rules:    BR-WRK-042 · BR-WRK-041 · BR-WRK-003 · BR-WRK-015 · BR-MET-110 ·
//           BR-WRK-057 · CLAUDE.md hard-won law 6 (diff the running app —
//           no gate looks at rendered output) · law 14 (the savepoint)
// ───────────────────────────────────────────────────────
/**
 * **Wave L's walkthrough — demo script L, clicked, and it is the phase-2 exit
 * test.**
 *
 * Law 6: *"Diff the running app against `05-prototype/`. No gate looks at
 * rendered output. Nine defects were found this way and by nothing else."*
 *
 * ⚠ **TWO BROWSER CONTEXTS, AND THE SECOND IS NOT DECORATION.** D. Ortiz works
 * a **390 × 844 phone** with the network switched off at the engine;
 * M. Torres accepts from a 1440-wide desktop. `Work-012` has no page header and
 * a full-width commit button, and every one of those is a thing that looks fine
 * at 1440 and is unusable at 390.
 *
 * ⚠ **THE SECOND SYNC IS ASSERTED AS A COUNT COMPARISON, NOT AS AN ABSENCE OF
 * ERROR.** *A re-sync of the same jobs adds nothing* is `WM-48`'s own worked
 * figure and the sentence this whole wave turns on. A check that only asserted
 * "the second sync did not throw" would pass over a server that cheerfully
 * applied everything twice — so the receipts, the completed orders and the
 * meter reads are COUNTED before and after, and the two numbers must be equal.
 *
 * ⚠ **AND EVERY NAVIGATION ASSERTS THAT IT ARRIVED, BY SCREEN ID.**
 * `DEF-WRK-4051`: two screens were unreachable for three commits with `tsc`,
 * 44 unit tests, the build and every gate green, because their route constants
 * carried a `/:tenant` prefix `App.tsx` adds for itself — so both fell through
 * to *"not built yet"*. A walkthrough is the ONLY thing that can see that
 * class, and only if it checks it ARRIVED rather than that navigation did not
 * throw. Hence `arrivedAt()` below: it asserts a WITNESS only that screen
 * renders, and separately rules out the not-built-yet placeholder by name — *this
 * is the wrong screen* and *this screen has not painted yet* are different
 * failures, and a check that conflates them wastes an hour.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   eval "$(10-scripts/proof-db.sh clone cr070l --export)"
 *   export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false
 *   (cd 06-backend && python manage.py runserver 127.0.0.1:8081 --noreload &)
 *   (cd 07-frontend && ./node_modules/.bin/vite build &&
 *      PORT=4281 API_PROXY_TARGET=http://127.0.0.1:8081 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4281 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr070-l-the-offline-day-and-the-read.mjs
 *
 * ── WHAT IT ASSERTS (demo script L, in its own order) ─────────────────────
 *   1  **THE PHONE HAS THE DAY, AND THE MARKER CARRIES A TIME** (step 1).
 *   2  **THE JOBS ARE WORKED AND CLOSED WITH THE NETWORK OFF** (step 2) —
 *      `context.setOffline(true)` is a real engine dropping real requests, and
 *      the closes are queued on the handset with **zero** network requests,
 *      counted by a request listener rather than assumed.
 *   3  **THE MARKER READS *N jobs to send*** (step 2, `US-WRK-044` TC-7) — and
 *      it counts JOBS, so three closed jobs read three and not forty-three.
 *   4  **ONE SYNC LANDS THE DAY** (step 3) — back online, the queue flushes and
 *      every order is `completed` with `completed_at` at the PHONE's time and
 *      `accepted_by` NULL. **Nothing activated**: zero meter reads.
 *   5  **A SECOND SYNC ADDS NOTHING** (step 4) — receipts, orders and reads
 *      counted before and after; the three numbers must be IDENTICAL.
 *   6  **THE SUPERVISOR SEES THEM AND ACCEPTS ONE** (steps 5–6) — `Work-009`
 *      is arrived at by screen id, the order is on it, and Accept is the real
 *      endpoint.
 *   7  **THE METER'S HISTORY CARRIES THE READ, DATED TO THE COMPLETION, WITH
 *      ITS UNIT** (step 7) — the wave's exit test (`BR-WRK-003`). The
 *      acceptance day and the completion day are DIFFERENT dates in the
 *      fixture, so this cannot pass by the two being the same.
 *   8  **THE LETTER IS REFUSED WITH ITS REASON, AND NOT SENT** (step 8,
 *      `BR-WRK-057`/`OQ-376`) — `queued: false`, a sentence, `tracks OQ-376`,
 *      and **never** filed as `notice`.
 *   9  **NO DATABASE ID, NO RULE ID, NO RAW CATALOGUE KEY** on the phone
 *      (B14 rules 31/32), and **no sideways scroll at 390**.
 *
 * ── WHAT IT DOES *NOT* ASSERT, AND WHY ────────────────────────────────────
 * **The savepoint is not here.** A browser cannot make two writes race inside
 * one transaction, and dressing a sequential retry up as that race would be a
 * check that cannot fail. It is proved where it can be —
 * `tests/test_us_wrk_044_sync_pg.py`, on real PostgreSQL under a role RLS
 * applies to — and it was proved by DELETING the savepoint and watching that
 * file go red. Stated here rather than quietly skipped.
 *
 * **Tenant isolation is not here**, for wave J's reason: a second utility
 * inside a browser walkthrough would make this file a seeder. It is
 * `test_us_wrk_044_sync_pg.py`'s `assert_rls_scoped` case.
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4281";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr070-l-the-offline-day";
const DESKTOP = { width: 1440, height: 1000 };
const PHONE = { width: 390, height: 844 };

/** Wave J's lesson, verbatim: once the field app's service worker registers,
 *  the page's network state never goes quiet the way Playwright waits for, so
 *  `networkidle` hangs after a SUCCESSFUL sign-in and looks like a broken
 *  screen. The route renders on the client anyway. */
const PHONE_WAIT = "domcontentloaded";

/** The handset's own times — `J65`'s. Deliberately NOT today: the whole point
 *  of `BR-WRK-003` is that the read lands on the day it was READ. */
const CLOSED_AT = "2026-03-15T16:07:00Z";
const READ_DAY = "2026-03-15";

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

const SIDEWAYS =
  "Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)";

const FORBIDDEN_IN_FIELD_COPY = [
  [/\bBR-[A-Z]{3}-\d{3,5}\b/, "a business-rule id"],
  [/\bOQ-(?:[A-Z]{3}-)?\d{3,5}\b/, "an open-question id"],
  [/\bDEF-(?:[A-Z]{3}-)?\d{3,5}\b/, "a defect id"],
  [/\bUS-[A-Z]{3}-\d{3,5}\b/, "a story id"],
  [/\bWork-0\d\d\b/, "a Work-nnn screen number"],
  [/\bWM-\d\d\b|\bWS-\d\d\b/, "a blueprint card id"],
  [/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/, "a database id"],
  [/\bwork\.mobile\.[a-z]/, "a raw catalogue key"],
];

async function signIn(page, tenant, email, password) {
  await page.goto(`${BASE}/${tenant}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", email);
  await page.fill("#signin-password", password);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });
}

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

/**
 * ⚠ **DID WE ACTUALLY ARRIVE — `DEF-WRK-4051`'s only possible witness.**
 * A registry entry proves a screen has an ENTRY; `"/:tenant" + ROUTE` is where
 * the app will actually look for it. When those disagree the door is dead and
 * every registry-based check stays green over it. So this reads the screen id
 * the component stamps on its own root, and a page that fell through to
 * *"not built yet"* has no such stamp.
 */
async function arrivedAt(page, witness, label) {
  await page.waitForTimeout(500);
  const [present, body] = await page.evaluate((selector) => {
    return [
      document.querySelector(selector) !== null,
      document.body.innerText.slice(0, 400),
    ];
  }, witness);
  // ⚠ **TWO ASSERTIONS, AND THE SECOND IS THE ONE THAT CATCHES A DEAD DOOR.**
  // A screen that fell through to the not-built-yet page renders no witness AND
  // renders that sentence; a screen that is merely slow renders neither yet. So
  // the placeholder is named explicitly rather than inferred from an absence —
  // *this is the wrong screen* and *this screen has not painted* are different
  // failures and a walkthrough that conflates them wastes an hour.
  const placeholder = body.includes("not built yet");
  check(
    present && !placeholder,
    `${label}: arrived at the screen itself` +
      (present && !placeholder
        ? ""
        : placeholder
          ? " — fell through to \"This screen is not built yet\" (DEF-WRK-4051's class: the registry and the mount disagree)"
          : ` — witness ${witness} is absent; page reads: ${body.replace(/\s+/g, " ").slice(0, 120)}`),
  );
  return present && !placeholder;
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const desk = await browser.newContext({ viewport: DESKTOP });
  const deskPage = await desk.newPage();
  const phone = await browser.newContext({ viewport: PHONE });
  const phonePage = await phone.newPage();

  try {
    await signIn(deskPage, TENANT, EMAIL, PASSWORD);
    await signIn(phonePage, TENANT, EMAIL, PASSWORD);

    // ── 0 · a technician, a template whose reading POSTS, and three orders ──
    //
    // ⚠ **SEEDED THROUGH THE PRODUCT'S OWN DOORS AND IDEMPOTENTLY**, wave H's
    // and wave J's shape. A seeded template database can be older than the wave
    // being proved, so a walkthrough that assumes its fixture reports a product
    // failure when the truth is an empty table.
    //
    // ⚠ **AND THE ORDERS ARE ANCHORED ON A METER**, because `BR-WRK-003` posts
    // a reading to the ORDER'S OWN meter and a job with no asset anchor is
    // refused by name. That refusal is correct and is asserted by the unit
    // tests; here it would just be a fixture that cannot reach the exit test.
    console.log("\n0 · a technician, a template whose reading posts, three orders on a meter");

    const choices = await api(deskPage, "GET", "/work/technicians?per=100");
    const me = (choices.body?.results ?? []).find(
      (row) => (row.email ?? "").toLowerCase() === EMAIL.toLowerCase(),
    );
    check(me !== undefined, `the signed-in login is in the technician picker (${EMAIL})`);
    if (me === undefined) throw new Error("cannot find the signed-in login among staff choices");

    // ⚠ **MATCHED BY NAME, NOT BY `user_id`, AND THAT IS NOT A PREFERENCE.**
    // `GET /work/crews` is `Work-023`'s ONE TABLE — people, crews and
    // contractors in one list — and a person row deliberately carries `name`
    // and `slug` and **no `user_id`**, because B14 rule 31 says the name is the
    // visible value and a link is built from the slug. So a lookup keyed on
    // `user_id` can never match, and wave J's walkthrough carries exactly that
    // lookup: it passed only because it ran against a database with no
    // technicians, took the create branch, and never exercised the find.
    // **Re-running it against its own output would fail**, which is the thing
    // worth knowing about a proof.
    let technician = null;
    const myName = (me.full_name ?? "").trim() || me.email;
    if (me.has_profile === true) {
      const crews = await api(deskPage, "GET", "/work/crews?per=100");
      technician = (crews.body?.results ?? []).find(
        (row) =>
          row.kind === "person" &&
          String(row.name ?? "").toLowerCase() === String(myName).toLowerCase(),
      );
    }
    if (technician === null || technician === undefined) {
      const made = await api(deskPage, "POST", "/work/technicians", {
        user_id: me.user_id,
        role_label: "Field technician",
      });
      check(made.status < 300, `a technician profile for the signed-in login (${made.status})`);
      technician = made.body;
    }
    check(technician?.id !== undefined, "a technician exists to assign to");
    if (technician?.id === undefined) throw new Error("no technician to assign to");

    // A meter to read — and it must be one whose REGISTER IS DENOMINATED IN
    // THE UNIT THE READING IS TAKEN IN.
    //
    // ⚠ **THE FIRST DRAFT TOOK THE FIRST ASSET IT FOUND AND THE ACCEPTANCE WAS
    // REFUSED — CORRECTLY, AND THE REFUSAL IS WORTH READING.** It picked
    // `BAT-0001`, a battery with no unit recorded, and metering's read pipeline
    // answered `unit_missing` and rolled the whole acceptance back. That is
    // `US-WRK-046` TC-5 happening for real — *"the read pipeline refuses the
    // value; the whole acceptance rolls back; the order stays on `Work-009`"* —
    // so the product was right and the fixture was wrong. A walkthrough that
    // "fixed" this by loosening the assertion would have thrown away a
    // guarantee; what it needed was a meter.
    // ⚠ **AND IT MUST BE A METER WITH NO READ ON 15 MARCH ALREADY, SO THIS FILE
    // CAN BE RUN TWICE.** `BR-MET-059` is one read per meter per date, and a
    // second run against the same database met that rule and was refused —
    // correctly. A proof that only works against a database it has never
    // touched is a proof somebody will one day be unable to reproduce, which is
    // the criticism this file makes of wave J's fixture four lines up. So the
    // meter is CHOSEN rather than taken: the first kWh meter whose history is
    // free on the day the reading is dated to.
    const assets = await api(deskPage, "GET", "/assets?per=200");
    const candidates = (assets.body?.results ?? []).filter(
      (a) => (a.asset_no ?? "") !== "" && (a.unit ?? "") === "kWh",
    );
    let meter;
    for (const candidate of candidates) {
      const history = await api(deskPage, "GET", `/assets/${candidate.id}/reads`);
      const taken = (history.body ?? []).some((r) => String(r.date ?? "").startsWith(READ_DAY));
      if (!taken) {
        meter = candidate;
        break;
      }
    }
    check(
      meter !== undefined,
      `an electric meter in kWh with no read on ${READ_DAY} yet (${meter?.asset_no})`,
    );
    if (meter === undefined) {
      throw new Error(`every kWh meter already has a read on ${READ_DAY} — clone a fresh database`);
    }

    // ⚠ **EXACTLY ONE reading that posts.** More than one is `OQ-WRK-1723` and
    // is refused BY NAME — correctly, because nothing says which meter the
    // second belongs to. The fixture is the case the product supports.
    const draft = await api(deskPage, "POST", "/work/templates", {
      name: `Wave L walkthrough — meter exchange ${Date.now()}`,
      service: "electric",
    });
    const templateId = draft.body?.id;
    check(templateId !== undefined, "a draft template is created");
    await api(deskPage, "PUT", `/work/templates/${templateId}/safety`, [
      { text: "Isolate at the service head before removal", is_mandatory: true },
      { text: "Check for backfeed / on-site generation", is_mandatory: true },
    ]);
    await api(deskPage, "PUT", `/work/templates/${templateId}/tasks`, [
      { title: "Confirm address and customer", est_minutes: 3 },
      { title: "Remove old meter", est_minutes: 12 },
    ]);
    await api(deskPage, "PUT", `/work/templates/${templateId}/readings`, [
      {
        prompt: "Final read on old meter",
        unit_of_measure: "kWh",
        min: 0,
        max: 99999,
        required: true,
        posts_as_meter_read: true,
      },
      { prompt: "New meter serial", unit_of_measure: "serial", required: false },
    ]);
    const published = await api(deskPage, "POST", `/work/templates/${templateId}/publish`);
    check(published.status < 300, `the template publishes (${published.status})`);

    const premises = await api(deskPage, "GET", "/premises?per=1");
    const premisesId = (premises.body?.results ?? [])[0]?.id;
    check(premisesId !== undefined, "there is a premises to raise an order on");

    // ⚠ **THE ORDERS STAND ON A BUILD AS WELL AS ON A METER, AND UNTIL THIS
    // LANE THEY DID NOT — WHICH QUIETLY DISARMED TWO CHECKS AT ONCE.**
    //
    // The fixture raised its three jobs on `premises_id` + `asset_id` and no
    // connection. `dispatch_communication` then returns at its very first
    // guard — *"an order with no build sends nothing, and says so"*
    // (`DEF-WRK-3635`) — with `no_connection: true`, and **never reaches the
    // queue at all.** So step 8's `BR-WRK-057` check, the one this wave's exit
    // test turns on, was passing on a job that never had a letter to send: its
    // assertion is an OR (`queued:false` *or* `OQ-376`) and the first half was
    // true for the wrong reason. A check that cannot tell *the platform
    // refused this letter* from *there was no letter* is not checking the rule.
    //
    // It also made the DESKTOP walk unreachable: `Work-009`'s eye builds its
    // link from `row.connection.home`, so a row with no build renders a
    // DISABLED eye and the drawer this wave is supposed to demonstrate cannot
    // be opened from the queue at all.
    //
    // So the jobs stand on BOTH: the build gives the letter and the drawer,
    // the meter gives the read. A cancelled build is skipped because
    // `dispatch_communication` refuses one by name and that is a third,
    // different answer.
    const builds = await api(deskPage, "GET", "/connections?per=100");
    const build = (builds.body?.results ?? []).find(
      (row) => row.state !== "cancelled" && row.home !== null && row.home !== undefined,
    );
    check(
      build !== undefined,
      `a build to stand the jobs on (${build?.connection_no} · ${build?.state})`,
    );
    if (build === undefined) {
      throw new Error("no usable build — the letter and the drawer both need one");
    }

    const orders = [];
    for (const label of ["WO-a", "WO-b", "WO-c"]) {
      const raised = await api(deskPage, "POST", "/work-orders", {
        connection_id: build.id,
        premises_id: premisesId,
        asset_id: meter.id,
        type: "Meter exchange",
        template_id: templateId,
      });
      check(raised.status < 300, `${label}: an order is raised (${raised.status})`);
      if (raised.body?.id === undefined) throw new Error("no order raised");
      await api(deskPage, "POST", `/work-orders/${raised.body.id}/assignments`, {
        act: "assign",
        technician_id: technician.id,
        window_start: "2026-03-15T09:15:00Z",
      });
      orders.push(raised.body);
    }
    check(orders.length === 3, `three jobs on D. Ortiz's day (${orders.length})`);

    // ── 1 · the phone has the day, and the marker carries a time ───────────
    console.log("\n1 · 08:12 — the phone has the day (Work-010)");
    await phonePage.goto(`${BASE}/${TENANT}/work/mobile`, { waitUntil: PHONE_WAIT });
    await arrivedAt(phonePage, '[data-testid="offline-marker"]', "Work-010");
    await phonePage.waitForTimeout(800);
    const marker = await phonePage
      .evaluate(() => document.querySelector('[data-testid="offline-marker"]')?.textContent ?? "")
      .catch(() => "");
    check(marker.trim().length > 0, `the marker is on the screen ("${marker.trim()}")`);
    await phonePage.screenshot({ path: join(OUT, "1-phone-today.png"), fullPage: true });

    // ── 2 · the signal goes, and three jobs are worked and CLOSED offline ──
    //
    // Every act goes through the phone's own queue. Nothing reaches the server:
    // the request listener below counts what actually left the page.
    // The safety rows, read while there is still a signal — a technician's
    // phone has them because the day was synced at 08:12 (`BR-WRK-042`: the
    // bundle is fetched at sync, never on tap).
    const safetyByOrder = new Map();
    for (const order of orders) {
      const list = await api(deskPage, "GET", `/work-orders/${order.id}/checklist`);
      safetyByOrder.set(
        order.id,
        (list.body?.safety ?? []).filter((row) => row.is_mandatory === true),
      );
    }
    check(
      [...safetyByOrder.values()].every((rows) => rows.length >= 2),
      "each job carries its mandatory safety rows",
    );

    console.log("\n2 · 08:13 — no signal. Three jobs worked and closed on the handset");
    // ⚠ **COUNT THE WRITES, NOT THE ATTEMPTS — AND THE DIFFERENCE IS THE
    // PRODUCT WORKING.** The close pane asks the server whether the job may
    // close (`close_readiness`) and that request is ATTEMPTED and fails; the
    // screen catches it and shows the verdict as unknown rather than as *you
    // may close*. Counting attempts would therefore fail this check over
    // correct, deliberate behaviour. What must be true is that **no WRITE left
    // the handset**, which is what the queue is for.
    let requestsWhileOffline = 0;
    const countRequests = (r) => {
      if (r.url().includes("/api/") && r.method() !== "GET") requestsWhileOffline += 1;
    };
    phonePage.on("request", countRequests);
    await phone.setOffline(true);

    for (const order of orders) {
      // ⚠ **NAVIGATED FROM INSIDE THE APP, NEVER BY `goto()` — AND THE FIRST
      // DRAFT GOT THIS WRONG IN A WAY THAT LOOKED LIKE A PRODUCT FAILURE.**
      // `page.goto()` while the context is offline is a COLD LOAD: the engine
      // cannot fetch the document or the bundle, so the close pane rendered as
      // a completely blank page and the run reported *the screen is absent* as
      // though the route were dead. It was not — the browser simply had no app.
      // A technician does not retype a URL in a meter pit; they tap, and a tap
      // is client-side routing inside a page that is already loaded. So the
      // history entry is pushed and React Router is told, with no document
      // fetch at all — which is also what makes the zero-requests assertion
      // below mean something instead of passing because nothing loaded.
      await phonePage.evaluate((path) => {
        window.history.pushState({}, "", path);
        window.dispatchEvent(new PopStateEvent("popstate"));
      }, `/${TENANT}/work/mobile/jobs/${order.id}/close`);
      const here = await arrivedAt(
        phonePage,
        '[data-screen="WRK-23"]',
        `Work-012 close (${order.order_no})`,
      );
      if (!here) break;
      // The offline label — `WS-12`, `BR-WRK-041`. Asserted BEFORE clicking,
      // because the label is the promise the app is making.
      const label = await phonePage.evaluate(
        () => document.querySelector("button.w-full")?.textContent ?? "",
      );
      check(
        label.includes("send when back online") || label.includes("·"),
        `${order.order_no}: the button says what will happen ("${label.trim()}")`,
      );
      // Queue the close through the SCREEN, exactly as a technician would.
      await phonePage.evaluate(() => {
        const radios = [...document.querySelectorAll('input[name="outcome"]')];
        if (radios[0]) radios[0].click();
      });
      await phonePage.waitForTimeout(150);
      await phonePage.evaluate(() => {
        const button = document.querySelector("button.w-full");
        if (button && !button.disabled) button.click();
      });
      await phonePage.waitForTimeout(400);
    }
    phonePage.off("request", countRequests);
    // ⚠ **PAIRED WITH A POSITIVE, BECAUSE ZERO REQUESTS IS ALSO WHAT A BLANK
    // PAGE LOOKS LIKE.** On its own this count passes when the app never
    // loaded at all — which is precisely how the first draft of this file hid
    // its own bug for a run. So it is asserted beside *the closes actually
    // queued*, and the two together say something: the work happened, and none
    // of it went over the wire.
    check(
      requestsWhileOffline === 0,
      `no WRITE reached the server while offline (${requestsWhileOffline} write(s))`,
    );
    const queuedOffline = await phonePage.evaluate(async () => {
      return new Promise((resolve) => {
        const open = indexedDB.open("sbh-work-mobile", 2);
        open.onerror = () => resolve(-1);
        open.onsuccess = () => {
          try {
            const tx = open.result.transaction("queue", "readonly");
            const all = tx.objectStore("queue").getAll();
            all.onsuccess = () => resolve(all.result.length);
            all.onerror = () => resolve(-1);
          } catch {
            resolve(-1);
          }
        };
      });
    });
    check(
      queuedOffline === orders.length,
      `the ${orders.length} closes are ON THE HANDSET, in its own store (${queuedOffline} queued)`,
    );
    await phonePage.screenshot({ path: join(OUT, "2-phone-closed-offline.png"), fullPage: true });

    // ── 3 · the marker counts JOBS, not items ─────────────────────────────
    console.log("\n3 · the marker reads N jobs to send (US-WRK-044 TC-7)");
    // The marker lives on `Work-010`, so go back to it — client-side, still
    // offline, which is the whole point of the marker existing.
    await phonePage.evaluate((path) => {
      window.history.pushState({}, "", path);
      window.dispatchEvent(new PopStateEvent("popstate"));
    }, `/${TENANT}/work/mobile`);
    await phonePage.waitForTimeout(900);
    const toSend = await phonePage.evaluate(
      () => document.querySelector('[data-testid="jobs-to-send"]')?.textContent ?? "",
    );
    check(
      /\b3\b/.test(toSend),
      `the marker counts JOBS and reads three ("${toSend.trim() || "absent"}")`,
    );

    // Nothing on the SERVER has moved yet — the closes are on the handset.
    const beforeSync = await api(deskPage, "GET", "/work-orders/awaiting-approval?per=100");
    const awaitingBefore = beforeSync.body?.results?.length ?? 0;

    // ── 4 · 17:40 · one sync ──────────────────────────────────────────────
    //
    // ⚠ **THE CLOSE CARRIES THE HANDSET'S TIME.** The batch is posted with
    // `captured_at` at 16:07 on 15 March; the server is running today. If
    // `completed_at` came out as *now*, the read in step 7 would land on the
    // wrong day and nothing on any screen would show it.
    console.log("\n4 · 17:40 — back online, one sync");
    await phone.setOffline(false);
    const synced = [];
    for (const order of orders) {
      // ⚠ **THE SAFETY TICKS COME FIRST, IN CAPTURE ORDER, AND THE SERVER
      // REFUSES THE CLOSE IF THEY DO NOT.** `BR-WRK-037` is re-derived on the
      // server from `ticked_at` and never from the client's word, so a batch
      // whose close arrived first would be refused BY NAME — which is what the
      // first draft of this walkthrough did, and the server was right.
      const safety = safetyByOrder.get(order.id) ?? [];
      const items = safety.map((row, i) => ({
        key: `ortiz-${order.id}-safety-${i}`,
        kind: "safety_tick",
        seq: i + 1,
        captured_at: "2026-03-15T15:15:00Z",
        payload: { safety_id: row.id },
      }));
      items.push({
        key: `ortiz-${order.id}-close`,
        kind: "close",
        seq: 20,
        captured_at: CLOSED_AT,
        payload: { outcome: "passed" },
      });
      const result = await api(phonePage, "POST", `/work/mobile/jobs/${order.id}/sync`, { items });
      check(result.status < 300, `${order.order_no}: the sync is accepted (${result.status})`);
      check(
        result.body?.accepted === items.length && result.body?.refused === 0,
        `${order.order_no}: all ${items.length} items accepted, none refused ` +
          `(${result.body?.accepted}/${result.body?.refused})` +
          (result.body?.refused
            ? ` — ${JSON.stringify(
                (result.body.items ?? []).find((i) => i.result === "refused")?.detail ?? {},
              ).slice(0, 160)}`
            : ""),
      );
      synced.push({ body: result.body, items });
    }

    const afterOne = await api(deskPage, "GET", "/work-orders/awaiting-approval?per=100");
    const awaitingAfterOne = afterOne.body?.results?.length ?? 0;
    check(
      awaitingAfterOne === awaitingBefore + 3,
      `three orders arrived in the approval queue (${awaitingBefore} → ${awaitingAfterOne})`,
    );

    // Every order completed, at the PHONE's time, and accepted by nobody.
    // ⚠ **`completed_at` IS READ OFF THE APPROVAL QUEUE, NOT THE ORDER DETAIL,
    // AND THAT IS THE BETTER PLACE FOR IT.** `GET /work-orders/{id}` does not
    // publish the column; `GET /work-orders/awaiting-approval` does, because it
    // is what `Work-009` shows a supervisor and what `waiting_days` counts
    // from. So this asserts the figure on the surface a person actually reads —
    // which is what law 6 asks of a walkthrough in the first place.
    const queueRows = afterOne.body?.results ?? [];
    for (const order of orders) {
      const row = queueRows.find((r) => String(r.order_no ?? "") === String(order.order_no));
      check(row !== undefined, `${order.order_no}: is on the approval queue`);
      check(
        String(row?.completed_at ?? "").startsWith("2026-03-15T16:07"),
        `${order.order_no}: completed_at is the HANDSET's 16:07 on 15 Mar, not the sync's clock (${row?.completed_at})`,
      );
      const detail = await api(deskPage, "GET", `/work-orders/${order.id}`);
      check(detail.body?.state === "completed", `${order.order_no}: state completed`);
      check(
        detail.body?.accepted_at === null || detail.body?.accepted_at === undefined,
        `${order.order_no}: accepted_by is still NULL — that NULL is the review queue`,
      );
    }

    // NOTHING ACTIVATED (`BR-MET-110`): no meter read exists yet.
    const readsBeforeAccept = await api(deskPage, "GET", `/assets/${meter.id}/reads`);
    const readCountBeforeAccept = (readsBeforeAccept.body ?? []).length;

    // ── 5 · a SECOND sync adds nothing — COUNTED, not assumed ─────────────
    //
    // ⚠ **THE ASSERTION THE WHOLE WAVE TURNS ON, AND IT IS A COMPARISON.**
    // *A re-sync of the same jobs adds nothing* (`WM-48`). A check that only
    // said "the second sync did not error" would pass over a server that
    // applied everything twice, which is precisely the failure being ruled out.
    console.log("\n5 · 17:41 — a second sync of the same queue adds NOTHING");
    for (const order of orders) {
      const sent = synced.find((s) => s.body?.work_order_id === String(order.id));
      const items = sent?.items ?? [];
      const again = await api(phonePage, "POST", `/work/mobile/jobs/${order.id}/sync`, { items });
      check(
        again.body?.duplicate === items.length && again.body?.accepted === 0,
        `${order.order_no}: every one of ${items.length} answered duplicate, accepted nothing ` +
          `(${again.body?.duplicate}/${again.body?.accepted})`,
      );
    }
    const afterTwo = await api(deskPage, "GET", "/work-orders/awaiting-approval?per=100");
    const awaitingAfterTwo = afterTwo.body?.results?.length ?? 0;
    check(
      awaitingAfterTwo === awaitingAfterOne,
      `the approval queue is IDENTICAL after the second sync (${awaitingAfterOne} → ${awaitingAfterTwo})`,
    );
    const readsAfterTwo = await api(deskPage, "GET", `/assets/${meter.id}/reads`);
    check(
      (readsAfterTwo.body ?? []).length === readCountBeforeAccept,
      `the meter's history is IDENTICAL after the second sync (${readCountBeforeAccept} → ${(readsAfterTwo.body ?? []).length})`,
    );

    // ── 6 · the supervisor sees them, and accepts one ON THE SCREEN ───────
    //
    // ⚠ **THIS WHOLE LEG WAS `fetch` UNTIL THIS LANE, AND THAT IS WHAT `L4`'s
    // DESKTOP HALF MEANT.** Wave L proved the SERVER: it opened `Work-009`,
    // then pressed Accept, read the meter's history and read the letter's fate
    // through three API calls made from inside the browser. **A request issued
    // from a page is not a thing the page DID** — every one of those three
    // could have passed over a screen with no Accept button, no read log and
    // no report of the letter at all, and two of them did exactly that.
    // So from here down the walkthrough CLICKS.
    console.log("\n6 · M. Torres opens the approval queue and accepts one — on the screen");
    await deskPage.goto(`${BASE}/${TENANT}/work/awaiting-approval`, { waitUntil: "networkidle" });
    await arrivedAt(deskPage, "[data-work-approvals]", "Work-009");
    const queueText = await deskPage.evaluate(() => document.body.innerText);
    check(
      queueText.includes(orders[0].order_no ?? "@@none@@"),
      `${orders[0].order_no} is on the approval queue screen`,
    );
    // ⚠ **PAIRED WITH A POSITIVE, BECAUSE STEP 6c COUNTS THIS LIST GOING DOWN.**
    // "One fewer row" means nothing unless the three were all there first: a
    // queue that never held them would satisfy the subtraction just as happily.
    const onQueueBefore = orders.filter((o) => queueText.includes(o.order_no ?? "@@none@@")).length;
    check(onQueueBefore === 3, `all three of the day's jobs are on the queue (${onQueueBefore}/3)`);
    const queueRowsBefore = await deskPage.evaluate(
      () => document.querySelectorAll("[data-work-approvals] tbody tr").length,
    );
    check(queueRowsBefore > 0, `the queue draws ${queueRowsBefore} row(s)`);
    await deskPage.screenshot({ path: join(OUT, "3-desktop-awaiting.png"), fullPage: true });

    // ⚠ **THE READING IS TYPED BEFORE THE ACCEPT**, because that is the order
    // the day happens in — the technician records it in the field and the
    // office accepts afterwards. This one stays an API call ON PURPOSE: it is
    // the TECHNICIAN's act, made on a handset that is not this browser, and
    // dressing it up as a desktop form would be the walkthrough inventing a
    // screen. What it feeds is the desktop half below, which is clicked.
    const checklist = await api(deskPage, "GET", `/work-orders/${orders[0].id}/checklist`);
    const posting = (checklist.body?.readings ?? []).find((r) => r.posts_as_meter_read === true);
    check(posting !== undefined, "the order carries a reading marked *becomes a meter read*");
    if (posting !== undefined) {
      const typed = await api(
        deskPage,
        "PUT",
        `/work-orders/${orders[0].id}/readings/${posting.id}`,
        { value: "1204", unit: "kWh" },
      );
      check(typed.status < 300, `1,204 kWh is recorded on the job (${typed.status})`);
    }

    // ── 6a · THE EYE IS A LINK AGAIN, AND THAT IS AN ASSERTION ────────────
    //
    // ⚠ **`Work-009`'s eye is DISABLED on a row with no build**, with the
    // reason *"the order detail is `Work-008` and is wave H's"*. Wave H landed
    // — `Work-008` is routed and live — so that particular hold has expired,
    // and it is hard-won law 2's MIRROR: a live screen behind a dead control.
    // This lane did not release it (the fixture now stands its jobs on a
    // build, so the drawer is reachable the way `L4` describes); what it does
    // is ASSERT the door is open, so a fixture that quietly loses its build
    // fails here rather than three steps later with a confusing message.
    const eye = deskPage.locator(`[data-work-approvals] tbody tr`, {
      hasText: orders[0].order_no ?? "@@none@@",
    }).locator("a");
    const eyeCount = await eye.count();
    check(
      eyeCount > 0,
      `${orders[0].order_no}'s row action is a LINK a supervisor can follow` +
        (eyeCount > 0 ? "" : " — it rendered as a disabled button, so the drawer cannot be opened"),
    );
    if (eyeCount === 0) {
      throw new Error("the approval queue offers no way through to the drawer");
    }
    await eye.last().click();
    await deskPage.waitForTimeout(1200);
    await arrivedAt(deskPage, "[data-work-orders-tab]", "Work-003 host (the build's home)");

    // ── 6b · *Nobody has accepted this yet* → Accept ──────────────────────
    const drawerBefore = await deskPage.evaluate(() => document.body.innerText);
    check(
      drawerBefore.includes("Nobody has accepted this yet"),
      "the drawer reads *Nobody has accepted this yet* — the NULL that IS the review queue" +
        (drawerBefore.includes("Nobody has accepted this yet")
          ? ""
          : ` — the drawer reads: ${drawerBefore.replace(/\s+/g, " ").slice(0, 200)}`),
    );
    const panelOpen = await deskPage.locator("[data-work-order-panel]").count();
    check(panelOpen === 1, `the work-order drawer is open (${panelOpen})`);
    await deskPage.screenshot({ path: join(OUT, "5-desktop-drawer-before.png"), fullPage: true });

    // The real button, pressed. `WorkingButton` renders a `<button>`; the
    // blocked form is a disabled Button with its reason beside it, so a
    // clickable one is itself the assertion that nothing was in the way.
    const markComplete = deskPage.locator("[data-work-order-panel] button", {
      hasText: "Mark complete",
    });
    const pressable = await markComplete.count();
    check(pressable > 0, `*Mark complete* is on the drawer (${pressable})`);
    const disabled = pressable > 0 ? await markComplete.first().isDisabled() : true;
    check(!disabled, "*Mark complete* is pressable — the field finished it and nobody accepted it");
    if (pressable > 0 && !disabled) {
      await markComplete.first().click();
    }
    await deskPage.waitForTimeout(2500);

    // ⚠ **THE PROOF THAT THE PRESS LANDED IS ON THE SCREEN, NOT IN A FETCH.**
    // The first draft of this line asked `GET /work-orders/{id}` for
    // `accepted_at` and got `undefined` — that reader does not publish the
    // column — so the check went RED over an acceptance that had in fact
    // succeeded. **A walkthrough asserting a key nothing serves fails over
    // correct data and reads exactly like a broken feature**, which is the
    // lesson wave L already wrote into step 7 about `read_at`/`current_value`
    // and which this lane promptly repeated one endpoint along.
    // So it reads what `L4` actually specifies: the sentence that WAS there is
    // gone, and a date stands in its place.
    const drawerAfter = await deskPage.evaluate(
      () => document.querySelector("[data-work-order-panel]")?.innerText ?? "",
    );
    check(
      !drawerAfter.includes("Nobody has accepted this yet"),
      "the PRESS landed — *Nobody has accepted this yet* is gone from the drawer",
    );
    check(
      /\d{2}[\/.-]\d{2}[\/.-]\d{2,4}|\d{4}-\d{2}-\d{2}/.test(drawerAfter),
      "and an acceptance DATE stands where that sentence was",
    );

    // ── 6c · WHAT THE PRESS DID, ON THE SCREEN — the letter, refused ──────
    //
    // ⚠ **THE POINT OF `L4`'s SECOND CLAUSE.** The drawer's own consequence
    // box promises *"tells the customer their service is live"*. On this
    // platform that letter is REFUSED at the queue (`OQ-376`: `connection` is
    // not a source kind the platform has a writer for), and until this lane
    // the screen said nothing at all — a supervisor read a promise that had
    // not been kept. `WorkOrderAcceptResult`'s docstring has demanded this in
    // capitals since 2026-09-04.
    const afterPress = await deskPage.evaluate(() => {
      const section = document.querySelector("[data-accept-outcome]");
      const letterCell = document.querySelector("[data-letter-sent]");
      const absent = document.querySelector("[data-accept-outcome] [data-absent]");
      return {
        present: section !== null,
        text: section === null ? "" : section.textContent ?? "",
        sent: letterCell === null ? null : letterCell.getAttribute("data-letter-sent"),
        tracks: absent === null ? null : absent.getAttribute("data-tracks"),
        body: document.body.innerText,
      };
    });
    check(afterPress.present, "the drawer now shows *What this acceptance did*");
    check(
      afterPress.sent === "no",
      `the letter is reported as NOT SENT on the screen (data-letter-sent=${afterPress.sent})`,
    );
    check(
      afterPress.text.includes("cannot be sent yet"),
      `and the screen says WHY, in a clerk's words ("${afterPress.text.replace(/\s+/g, " ").trim().slice(0, 120)}")`,
    );
    // ⚠ **THE REFUSAL IS THE PLATFORM'S, NOT "this job had no build".** Those
    // are two different answers and `DEF-WRK-3635` is the reason they must not
    // share a sentence. The question travels in a DOM attribute, which is not
    // a visible value (B14 rule 31) and is exactly what lets this be checked.
    check(
      afterPress.tracks === "OQ-376",
      `it is the QUEUE's refusal being reported, not a missing build (tracks=${afterPress.tracks})`,
    );
    // B14 rule 32 — the server's own refusal names the SOURCE_TYPES constant
    // and lists its whole vocabulary. It must never reach a clerk.
    check(
      !afterPress.body.includes("SOURCE_TYPES") &&
        !afterPress.body.includes("is not a source kind"),
      "the platform's internal refusal text is NOT printed at the supervisor",
    );
    check(
      !afterPress.body.includes("OQ-376"),
      "and neither is the question's id — B14 rules 31 and 32 hold on the desktop too",
    );
    await deskPage.screenshot({ path: join(OUT, "6-desktop-drawer-after.png"), fullPage: true });

    // ── 6d · THE JOB LEAVES THE QUEUE — counted, and paired ───────────────
    console.log("\n6d · the accepted job leaves *Awaiting approval*");
    await deskPage.goto(`${BASE}/${TENANT}/work/awaiting-approval`, { waitUntil: "networkidle" });
    await arrivedAt(deskPage, "[data-work-approvals]", "Work-009");
    const queueAfter = await deskPage.evaluate(() => document.body.innerText);
    check(
      !queueAfter.includes(orders[0].order_no ?? "@@none@@"),
      `${orders[0].order_no} is GONE from the queue — a person accepted it`,
    );
    // ⚠ **THE POSITIVE THAT MAKES THE ABSENCE MEAN SOMETHING.** An empty queue
    // satisfies "it is gone" perfectly, and so does a broken list. The other
    // two jobs of the same day must still be standing there.
    const stillWaiting = orders
      .slice(1)
      .filter((o) => queueAfter.includes(o.order_no ?? "@@none@@")).length;
    check(
      stillWaiting === 2,
      `and the day's other two jobs are still waiting (${stillWaiting}/2) — the queue lost ONE row, not its contents`,
    );

    // ── 7 · THE EXIT TEST — the read is on the meter, dated to the day it
    //        was READ, with its unit ────────────────────────────────────────
    console.log("\n7 · the meter's history: 1,204 kWh dated 15 Mar, with its unit");
    const history = await api(deskPage, "GET", `/assets/${meter.id}/reads`);
    const rows = history.body ?? [];
    check(
      rows.length === readCountBeforeAccept + 1,
      `exactly one read was added by the acceptance (${readCountBeforeAccept} → ${rows.length})`,
    );
    // ⚠ **`date`, `reading` AND `unit` — the keys `Work-016`'s history actually
    // publishes** (`assets.selectors._fold_row`). The first draft read
    // `read_at` / `current_value`, which are the COLUMN names, and got
    // `undefined` for both — an assertion against a key nothing serves fails
    // over correct data and reads exactly like a missing feature.
    const landed = rows.find((r) => String(r.date ?? "").startsWith(READ_DAY));
    check(
      landed !== undefined,
      `the read is dated ${READ_DAY} — the day it was READ, not the day it was accepted` +
        (landed === undefined ? ` (dates present: ${rows.map((r) => r.date).join(", ")})` : ""),
    );
    check(
      (landed?.unit ?? "") === "kWh",
      `the read carries its unit (${landed?.unit ?? "none"}) — hard rule 3`,
    );
    check(
      String(landed?.reading ?? "").startsWith("1204"),
      `the read is the number the technician typed (${landed?.reading})`,
    );
    // ⚠ **AND THE TWO DATES ARE GENUINELY DIFFERENT**, or this case could pass
    // by the acceptance happening to fall on 15 March. The server's clock is
    // today; the read is dated to the completion the handset recorded.
    const acceptedToday = new Date().toISOString().slice(0, 10);
    check(
      acceptedToday !== READ_DAY,
      `the acceptance day (${acceptedToday}) is not the read day (${READ_DAY}) — so this cannot pass by coincidence`,
    );

    // ── 7b · THE METER'S HISTORY, ON THE SCREEN A SUPERVISOR OPENS ────────
    //
    // ⚠ **STEP 7 ABOVE READS THE API AND THIS READS THE TABLE, AND UNTIL
    // `DEF-MET-4101` WAS FIXED THE TWO DISAGREED — WHICH IS THE WHOLE ARGUMENT
    // FOR DOING BOTH.** A read's date is a CALENDAR DATE and metering
    // normalises every one to 00:00:00Z on purpose (it is what makes the
    // per-date uniqueness key work). `assets/selectors._fold_row` used to serve
    // that value as a RAW INSTANT, and `DateCell` — correctly, by its own
    // documented contract — converts an instant into the tenant's timezone.
    // Brazos Bend is America/Chicago, so the read the API dated `2026-03-15`
    // was DRAWN as **03/14/2026**. Every check in this repo compared UTC dates,
    // so nothing could see it; it took rendering the page. **Closed 2026-09-06:
    // the fold now serves the calendar date, so the table and the API agree.**
    // This step stays, and it is the check that keeps them agreeing.
    console.log("\n7b · the meter's history on the screen (Work-016 / the asset's Reads tab)");
    await deskPage.goto(`${BASE}/${TENANT}/assets/${meter.id}?tab=reads`, {
      waitUntil: "networkidle",
    });
    await arrivedAt(deskPage, "[data-asset-reads]", "the meter's read log");
    const readLog = await deskPage.evaluate(
      () => document.querySelector("[data-asset-reads]")?.innerText ?? "",
    );
    check(
      readLog.includes("1204") || readLog.includes("1,204"),
      `the reading D. Ortiz typed is ON THE PAGE (${readLog.replace(/\s+/g, " ").slice(0, 140)})`,
    );
    // ⚠ **THE DATE CELL, ASSERTED OUTRIGHT — `DEF-MET-4101` IS CLOSED.**
    // This branch used to accept `03/14/2026` and fail loudly the day the fold
    // was fixed, which is hard-won law 2's rule for a hold: the test that fires
    // when the hold expires, written in the same commit. It fired, it named the
    // fix, and this is that line collected. **The screen must now draw the day
    // the job was COMPLETED**, and the day before it is the defect by name.
    const completionDay = "03/15/2026";
    const theDefectsDay = "03/14/2026";
    check(
      readLog.includes(completionDay),
      `the read log draws ${completionDay} — the day the job was completed, in ` +
        `the tenant's own timezone (America/Chicago)`,
    );
    check(
      !readLog.includes(theDefectsDay),
      `it does NOT draw ${theDefectsDay} — that is DEF-MET-4101, a calendar date ` +
        `served as an instant and converted west of UTC`,
    );
    await deskPage.screenshot({ path: join(OUT, "7-desktop-meter-history.png"), fullPage: true });

    // ── 8 · the letter is REFUSED with its reason, and not sent ────────────
    //
    // The SCREEN half of this is step 6c, which read it off the drawer after a
    // real press. This is the other half: nothing was FILED. `BR-WRK-057` is
    // as much about the message that must not exist as about the sentence that
    // must be shown.
    console.log("\n8 · the *your service is live* letter — refused, and filed nowhere");
    const outbound = await api(deskPage, "GET", "/outbound?per=200");
    const messages = outbound.body?.results ?? [];
    // ⚠ **A ZERO PAIRED WITH A POSITIVE.** "No connection message was filed"
    // passes just as happily over an endpoint that returned nothing at all, a
    // 403, or an empty utility — so the same list must be shown to be a REAL
    // list first. If it is legitimately empty the pairing says so rather than
    // claiming a guarantee it cannot make.
    check(
      outbound.status === 200,
      `the outbound message log answers (${outbound.status}) — ${messages.length} row(s)`,
    );
    const connectionKinds = messages.filter((m) => m.source_type === "connection");
    check(
      connectionKinds.length === 0,
      `no message was filed under the kind the platform does not have (${connectionKinds.length})`,
    );
    // The tempting wrong fix, asserted as an absence BY NAME: a *your service
    // is live* letter filed as `notice` would reach the customer with the
    // right words and make every monthly count of notices wrong, silently.
    const liveNotices = messages.filter(
      (m) =>
        m.source_type === "notice" &&
        String(m.source_id ?? "") === String(build.id) ,
    );
    check(
      liveNotices.length === 0,
      `and none was misfiled as a notice against this build (${liveNotices.length})`,
    );
    if (messages.length === 0) {
      console.log(
        "   ⓘ the outbound log is EMPTY on this database, so the two zeros above are weak — " +
          "the letter's refusal is proved on the drawer in step 6c, which is a positive.",
      );
    }

    // ── 9 · nothing a technician must never be shown, and no sideways scroll
    console.log("\n9 · B14 rules 31 and 32 on the phone, and no sideways scroll at 390");
    for (const [label, url] of [
      ["Work-010", `${BASE}/${TENANT}/work/mobile`],
      ["Work-012", `${BASE}/${TENANT}/work/mobile/jobs/${orders[0].id}/close`],
    ]) {
      await phonePage.goto(url, { waitUntil: PHONE_WAIT });
      await phonePage.waitForTimeout(400);
      const visible = await phonePage.evaluate(() => document.body.innerText);
      for (const [pattern, what] of FORBIDDEN_IN_FIELD_COPY) {
        const hit = visible.match(pattern);
        check(hit === null, `${label}: no ${what}${hit === null ? "" : ` — found ${hit[0]}`}`);
      }
      const sideways = await phonePage.evaluate(SIDEWAYS);
      check(sideways === 0, `${label}: no sideways scroll at 390 (${sideways}px)`);
    }
    await phonePage.screenshot({ path: join(OUT, "4-phone-close.png"), fullPage: true });
  } finally {
    await browser.close();
  }

  console.log(`\nscreenshots → ${OUT}`);
  if (failures.length > 0) {
    console.log(`\n⛔ ${failures.length} failed:`);
    for (const f of failures) console.log(`   · ${f}`);
    process.exit(1);
  }
  console.log("\n✓ every check passed");
})();
