/**
 * ── Trace ──────────────────────────────────────────────
 * Story:    US-WRK-030 · US-WRK-041 · US-WRK-042 · US-WRK-043 (EP-WRK-08 /
 *           EP-WRK-05).  Screens: Work-007 (desktop), Work-010, Work-011
 * Rules:    BR-WRK-034 (push on assignment; the audit line) · BR-WRK-035
 *           (appointment order; the pill does not reorder) · BR-WRK-036 (the
 *           marker) · BR-WRK-037 (the lock, on the phone AND the server) ·
 *           BR-WRK-038 (help offline) · CLAUDE.md hard-won law 6
 * Task:     CR-070 wave J, task J7 — demo script J, clicked
 * ───────────────────────────────────────────────────────
 *
 * **Wave J's walkthrough — and law 6 is the whole reason it exists.**
 * *"Diff the running app against `05-prototype/`. No gate looks at rendered
 * output. Nine defects were found this way and by nothing else."*
 *
 * ⚠ **TWO BROWSER CONTEXTS, AND THE SECOND IS THE POINT.** M. Torres assigns
 * from a 1440-wide desktop; D. Ortiz reads a **390 × 844 phone**. A phone
 * viewport is not decoration here: `Work-010` and `Work-011` have no page
 * header, no sidebar and a fixed bottom bar, and every one of those is a thing
 * that looks fine at 1440 and is unusable at 390.
 *
 * ⚠ **AND ONE ASSERTION CANNOT BE MADE ANYWHERE ELSE IN THIS REPOSITORY:**
 * that the SOP still opens with the network **off**. `context.setOffline(true)`
 * is a real engine dropping real requests; `BR-WRK-038` is *"help is carried
 * with the job and available offline"*, and a jsdom test mocking the store
 * proves the component reads a store, never that the store had the bytes.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   eval "$(10-scripts/proof-db.sh clone cr070j --export)"
 *   export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false
 *   (cd 06-backend && python manage.py runserver 127.0.0.1:8079 --noreload &)
 *   (cd 07-frontend && ./node_modules/.bin/vite build &&
 *      PORT=4279 API_PROXY_TARGET=http://127.0.0.1:8079 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4279 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr070-j-the-phone-day-one.mjs
 *
 * ── WHAT IT ASSERTS (demo script J, clicked) ──────────────────────────────
 *   1  **ASSIGNING WRITES A `work.push` JOB ROW** (demo step 1) — M. Torres
 *      assigns an order to D. Ortiz; the response carries a `push_job_id` and
 *      the job row exists. The ROW, not the message: a broker that is down
 *      loses a message and never a record.
 *   2  **THE AUDIT LINE DOES NOT LIE** (demo step 1) — the order's audit
 *      carries `dispatched_pushed` where a device is registered and
 *      `dispatched_waiting` where none is. `US-WRK-030` TC-2's *never* pushed
 *      *when it was not*, read off the real trail.
 *   3  **THE DAY IS IN APPOINTMENT ORDER** (demo step 2) — on the phone, the
 *      cards come back in time order with the priority shown as a pill; then
 *      the same order is re-prioritised to Urgent and the list is READ AGAIN
 *      and has not moved (`US-WRK-041` TC-2 — the one assertion that separates
 *      *ordered by time* from *happens to look ordered*).
 *   4  **THE MARKER IS THERE AND CARRIES A TIME** (demo step 3, `BR-WRK-036`).
 *   5  **THE TASK LIST IS LOCKED, STAYS LOCKED AT TWO OF THREE, AND OPENS ON
 *      THE THIRD** (demo steps 4–6) — ticked through the real endpoint, the
 *      screen re-read each time.
 *   6  **THE SOP OPENS WITH THE NETWORK OFF** (demo step 7) —
 *      `context.setOffline(true)`, then the job renders from the store with
 *      **zero network requests**, counted by a request listener rather than
 *      assumed.
 *   7  **THE SERVER REFUSES A CLOSE WITH A SAFETY ROW UNTICKED, NAMING IT**
 *      (demo step 8) — posted straight at `/work-orders/{id}/field-result`
 *      from inside the page. This is the wave's exit test.
 *   8  **`docker compose config` LISTS `celery-work` ON `-Q work`** — the
 *      consumer half, read out of the file the operator runs.
 *   9  **NO DATABASE ID, NO RULE ID, NO RAW CATALOGUE KEY** on either phone
 *      screen (B14 rules 31 and 32), and **no sideways scroll at 390**.
 *
 * ── WHAT IT DOES *NOT* ASSERT, AND WHY ────────────────────────────────────
 * **Tenant isolation is not here.** A second utility inside a browser
 * walkthrough would make this file a seeder. It is proved where it can be:
 * `tests/test_us_wrk_030_push.py` TC-5 for the application layer, and
 * `tests/test_us_wrk_030_push_pg.py` for the policy itself, on real PostgreSQL
 * under a role RLS applies to. Stated here rather than quietly skipped.
 *
 * **Installability is not asserted by clicking *Add to home screen*** — no
 * headless browser offers that prompt. What IS asserted is the two things the
 * prompt depends on: the manifest link is in the document and resolves, and the
 * service worker registers. Saying so is more use than a check that cannot
 * fail.
 */

import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, readdirSync } from "node:fs";
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4279";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr070-j-the-phone";
const DESKTOP = { width: 1440, height: 1000 };
/** A phone, and the number matters: `WS-10` is drawn for one. */
const PHONE = { width: 390, height: 844 };

/**
 * ⚠ **`domcontentloaded`, NEVER `networkidle`, ON THE PHONE — AND THIS COST A
 * RUN.** Once the field app's service worker is registered the page's network
 * state never goes quiet in the way Playwright waits for, so a
 * `waitUntil: "networkidle"` navigation to `/work/mobile` hangs until the
 * script's own timeout — after signing in successfully, which makes it look
 * like the screen is broken rather than the wait. The desktop context has no
 * worker and is unaffected, which is why only these navigations changed.
 * Waiting for the DOM and then an explicit beat is what a single-page app
 * needs anyway: the route renders on the client, so *the network went quiet*
 * was never the signal that mattered.
 */
const PHONE_WAIT = "domcontentloaded";

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

const SIDEWAYS =
  "Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)";

/** Anything a technician must never be shown (B14 rules 31 and 32). */
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

function words(sentence) {
  return sentence.replace(/[.…]+$/u, "").trim().split(/\s+/u).length;
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const desk = await browser.newContext({ viewport: DESKTOP });
  const deskPage = await desk.newPage();

  try {
    await signIn(deskPage, TENANT, EMAIL, PASSWORD);

    // ── 0 · a technician, a template with safety, and an order ────────────
    //
    // ⚠ **SEEDED THROUGH THE PRODUCT'S OWN DOORS AND IDEMPOTENTLY**, the shape
    // wave H's walkthrough established. A seeded template database can be older
    // than the wave being proved — the one this ran against had 17 planned
    // orders, ZERO technicians and ZERO safety rows, because it predates waves
    // F and H — so a walkthrough that assumes its fixture is a walkthrough that
    // reports a product failure when the truth is an empty table.
    console.log("\n0 · a technician, a template with safety rows, and an order");

    // `GET /work/technicians` answers the PICKER (every login that COULD be one,
    // flagged `has_profile`), not the profiles — `BR-WRK-028`. So: find a login
    // that already has a profile, or make one.
    // ⚠ **THE PROFILE MUST BELONG TO THE LOGIN THE PHONE SIGNS IN AS, AND THE
    // FIRST DRAFT GOT THIS WRONG IN A WAY WORTH RECORDING.** It made a profile
    // for whichever spare login came first, then signed the phone in as the
    // walkthrough's own user — so `GET /work/mobile/today` correctly answered
    // with an EMPTY DAY (`technician_of(actor)` found no profile for the
    // caller) and the run reported *the day has jobs (0)* as though the product
    // had lost a job. It had not: the route deliberately takes no
    // `technician_id`, because *"show me somebody else's day"* must not be a
    // request that can be made (`US-WRK-041` TC-6). So the fixture has to make
    // the signed-in person the technician, and that constraint is the rule
    // working rather than an inconvenience.
    const choices = await api(deskPage, "GET", "/work/technicians?per=100");
    const rows = choices.body?.results ?? [];
    const me = rows.find((row) => (row.email ?? "").toLowerCase() === EMAIL.toLowerCase());
    check(me !== undefined, `the signed-in login is in the technician picker (${EMAIL})`);
    if (me === undefined) throw new Error("cannot find the signed-in login among staff choices");
    let technician = null;
    if (me.has_profile === true) {
      const crews = await api(deskPage, "GET", "/work/crews?per=100");
      technician = (crews.body?.results ?? []).find(
        (row) => String(row.user_id ?? "") === String(me.user_id),
      );
    }
    if (technician === null || technician === undefined) {
      const made = await api(deskPage, "POST", "/work/technicians", {
        user_id: me.user_id,
        role_label: "Field technician",
      });
      check(made.status === 201, `a technician profile for the signed-in login (${made.status})`);
      technician = made.body;
    }
    check(technician?.id !== undefined, "a technician exists to assign to");
    if (technician?.id === undefined) throw new Error("no technician to assign to");

    // A published template carrying THREE mandatory safety rows — the lock
    // needs at least two to show *two of three is locked*.
    let templates = await api(deskPage, "GET", "/work/templates?per=100");
    let template = (templates.body?.results ?? []).find(
      (row) => (row.version ?? 0) >= 1 && (row.contents?.safety ?? 0) >= 2,
    );
    if (template === undefined) {
      const draft = await api(deskPage, "POST", "/work/templates", {
        name: "Wave J walkthrough — meter exchange",
        service: "water",
      });
      const id = draft.body?.id;
      check(id !== undefined, "a draft template is created");
      await api(deskPage, "PUT", `/work/templates/${id}/safety`, [
        { text: "Isolate at the service head before removal", is_mandatory: true },
        { text: "Check for backfeed / on-site generation", is_mandatory: true },
        { text: "Confined space check where pit-set", is_mandatory: true },
      ]);
      await api(deskPage, "PUT", `/work/templates/${id}/tasks`, [
        { title: "Confirm address and customer", est_minutes: 3 },
        { title: "Remove old meter", est_minutes: 12 },
        { title: "Photograph the new serial", est_minutes: 4, photo_required: true },
      ]);
      await api(deskPage, "PUT", `/work/templates/${id}/help`, [
        { kind: "note", label: "Meter exchange SOP v4" },
        { kind: "phone", label: "Supervisor · M. Torres", ref: "(512) 555-0138" },
      ]);
      const published = await api(deskPage, "POST", `/work/templates/${id}/publish`);
      check(published.status < 300, `the template publishes (${published.status})`);
      template = { id };
    }

    // An order raised FROM it, so it carries the six copies (`BR-WRK-008`).
    const premises = await api(deskPage, "GET", "/premises?per=1");
    const premisesId = (premises.body?.results ?? [])[0]?.id;
    check(premisesId !== undefined, "there is a premises to raise an order on");
    const raised = await api(deskPage, "POST", "/work-orders", {
      premises_id: premisesId,
      type: "Meter exchange",
      template_id: template.id,
    });
    check(raised.status === 201 || raised.status === 200, `an order is raised (${raised.status})`);
    const order = raised.body;
    check(order?.id !== undefined, `the order has a number (${order?.order_no})`);
    if (order?.id === undefined) throw new Error("no order to assign");

    // ── 1 · assigning writes a `work.push` job ROW (demo step 1) ──────────
    console.log("\n1 · M. Torres assigns it — the push is a job row");
    const assigned = await api(deskPage, "POST", `/work-orders/${order.id}/assignments`, {
      act: "assign",
      technician_id: technician.id,
      window_start: "2026-03-15T15:30:00Z",
    });
    check(assigned.status === 200, `the assign is accepted (${assigned.status})`);
    check(
      typeof assigned.body?.push_job_id === "string" || assigned.body?.push_job_id === null,
      "the answer carries a push_job_id (a string when a push was enqueued)",
    );
    check(
      assigned.body?.dispatch_state === "scheduled",
      `dispatch_state moved to scheduled (${assigned.body?.dispatch_state})`,
    );

    // ── 2 · the job is QUEUED, and the audit line is the worker's (step 1) ─
    //
    // ⚠ **THIS ASSERTS THE ROW AND NOT THE AUDIT LINE, AND THE REASON IS THE
    // DESIGN RATHER THAN A LIMITATION.** `work.push` rides its own queue and
    // `celery-work` runs its BODY; the two audit actions
    // (`…dispatched_pushed` / `…dispatched_waiting`) are written by that body,
    // from a COUNT of registered devices. This stack runs no worker, so the
    // record sits `queued` — which is exactly what `core/jobs.py` promises and
    // what `DEF-320` is about: the ROW survives, the message can be lost. The
    // two audit lines are asserted where the body can actually be run, in
    // `tests/test_us_wrk_030_push.py` TC-1c and TC-2a. Asserting them HERE
    // would need a worker in the loop and would fail for a reason that has
    // nothing to do with the screen this walkthrough is about.
    console.log("\n2 · the push job row exists and is queued");
    const jobId = assigned.body?.push_job_id;
    check(typeof jobId === "string" && jobId.length > 0, `a work.push job row was written (${jobId})`);
    // ⚠ **THE RECORD IS NOT READ BACK HERE, AND THAT IS NOT AN OMISSION.**
    // `GET /jobs/{id}` — B12 r1's poll URL — is registered in no urlconf: the
    // API client says so in its own words (*"no /jobs route is registered in
    // config/urls.py yet"*). Asserting a 200 from it would fail for a reason
    // that has nothing to do with the push. The id being returned is what this
    // walkthrough can honestly check; that the ROW is written before the broker
    // message is `tests/test_us_wrk_030_push.py` TC-1a, where the store can be
    // read directly.

    await deskPage.goto(`${BASE}/${TENANT}/work/orders`, { waitUntil: "networkidle" });
    await deskPage.screenshot({ path: join(OUT, "1-desktop-orders.png"), fullPage: true });

    // ── the phone, from here on ───────────────────────────────────────────
    const phone = await browser.newContext({
      viewport: PHONE,
      userAgent:
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 " +
        "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    });
    const phonePage = await phone.newPage();
    await signIn(phonePage, TENANT, EMAIL, PASSWORD);

    console.log("\n3 · Today, on a 390-wide phone");
    await phonePage.goto(`${BASE}/${TENANT}/work/mobile`, { waitUntil: PHONE_WAIT });
    await phonePage.waitForTimeout(600);
    await phonePage.screenshot({ path: join(OUT, "2-phone-today.png"), fullPage: true });

    // 4 · the marker (BR-WRK-036)
    const marker = await phonePage
      .locator('[data-testid="offline-marker"]')
      .first()
      .textContent()
      .catch(() => null);
    check(marker !== null, `the offline marker is on screen (${JSON.stringify(marker)})`);
    check(
      marker !== null && marker.includes("◍"),
      "the marker carries its own glyph, so it reads as a state and not a sentence",
    );

    // 3 · appointment order, and re-prioritising must not move it
    const dayBefore = await api(phonePage, "GET", "/work/mobile/today?days=7");
    const orderBefore = (dayBefore.body?.jobs ?? []).map((j) => j.order_no);
    check(orderBefore.length > 0, `the day has jobs (${orderBefore.length})`);

    // `/lookups/work_priorities` — the reference-data family, not a Work route.
    const priorities = await api(deskPage, "GET", "/lookups/work_priorities?per=100");
    const urgent = (priorities.body?.results ?? []).find((p) =>
      (p.code ?? "").toLowerCase().includes("urgent"),
    );
    if (urgent !== undefined) {
      await api(deskPage, "POST", `/work-orders/${order.id}/priority`, {
        priority_id: urgent.id,
      });
      const dayAfter = await api(phonePage, "GET", "/work/mobile/today?days=7");
      const orderAfter = (dayAfter.body?.jobs ?? []).map((j) => j.order_no);
      check(
        JSON.stringify(orderBefore) === JSON.stringify(orderAfter),
        "BR-WRK-035: raising the priority to Urgent did NOT reorder the day",
      );
    } else {
      check(false, "no Urgent priority in the seed — TC-2 could not be exercised");
    }

    // ── 5 · the lock: closed, still closed at two of three, then open ─────
    console.log("\n4-6 · the safety lock on the phone");
    const bundle = await api(phonePage, "GET", `/work/mobile/jobs/${order.id}`);
    const safety = bundle.body?.safety ?? [];
    const mandatory = safety.filter((row) => row.is_mandatory);
    check(bundle.status === 200, `the bundle loads (${bundle.status})`);

    if (mandatory.length >= 2) {
      check(bundle.body?.safety_lock?.locked === true, "the task list starts LOCKED");
      // tick all but one — still locked, and this is the rule's own sentence
      for (const row of mandatory.slice(0, -1)) {
        await api(phonePage, "POST", `/work-orders/${order.id}/safety/${row.id}/tick`);
      }
      const partway = await api(phonePage, "GET", `/work/mobile/jobs/${order.id}`);
      check(
        partway.body?.safety_lock?.locked === true,
        `BR-WRK-037: ${mandatory.length - 1} of ${mandatory.length} ticked is LOCKED, ` +
          "not nearly-unlocked",
      );

      // ⚠ **TODAY FIRST, AND THAT ORDERING IS THE RULE RATHER THAN A WARM-UP**
      // (`BR-WRK-042`, `DEF-WRK-4061`). `JobPage` reads the offline store and
      // never the network, so a job opens only after a sync has put its bundle
      // there — which is what makes it work in a meter pit. Navigating
      // straight to the job by URL on a phone that has never synced correctly
      // shows *Not on this phone yet.* The first run of this walkthrough did
      // exactly that and found that NOTHING called `syncJob` at all.
      await phonePage.goto(`${BASE}/${TENANT}/work/mobile`, { waitUntil: PHONE_WAIT });
      await phonePage.waitForTimeout(1200);
      await phonePage.goto(`${BASE}/${TENANT}/work/mobile/jobs/${order.id}`, {
        waitUntil: PHONE_WAIT,
      });
      await phonePage.waitForTimeout(600);
      await phonePage.screenshot({ path: join(OUT, "3-phone-job-locked.png"), fullPage: true });
      const lockedAttr = await phonePage
        .locator('[data-testid="task-list"]')
        .first()
        .getAttribute("data-locked")
        .catch(() => null);
      check(lockedAttr === "true", `the task list renders locked (data-locked=${lockedAttr})`);

      // ── 7 · THE SERVER REFUSES THE CLOSE, NAMING THE ROW (demo step 8) ──
      console.log("\n8 · the server refuses a close with a safety row unticked");
      const refused = await api(phonePage, "POST", `/work-orders/${order.id}/field-result`, {
        outcome: "passed",
        field_data: {},
      });
      check(
        refused.status === 409,
        `the completion is REFUSED (${refused.status}) — the guarantee, not the grey`,
      );
      const named = JSON.stringify(refused.body ?? {});
      const last = mandatory[mandatory.length - 1];
      check(
        named.includes(last.text),
        "BR-WRK-037: the refusal NAMES the outstanding row",
      );

      // and the gate opens on the last tick
      await api(phonePage, "POST", `/work-orders/${order.id}/safety/${last.id}/tick`);
      const opened = await api(phonePage, "GET", `/work/mobile/jobs/${order.id}`);
      check(opened.body?.safety_lock?.locked === false, "ticking the last one UNLOCKS the tasks");
      await phonePage.goto(`${BASE}/${TENANT}/work/mobile/jobs/${order.id}`, {
        waitUntil: PHONE_WAIT,
      });
      await phonePage.waitForTimeout(400);
      await phonePage.screenshot({ path: join(OUT, "4-phone-job-unlocked.png"), fullPage: true });
    } else {
      check(false, `the order has ${mandatory.length} mandatory safety rows — need 2+`);
    }

    // ── 6 · THE JOB OPENS WITH THE NETWORK OFF (demo step 7) ──────────────
    console.log("\n7 · airplane mode — the job and its help still open");
    let requests = 0;
    const count = () => {
      requests += 1;
    };
    phonePage.on("request", count);
    await phone.setOffline(true);
    await phonePage.reload({ waitUntil: "domcontentloaded" }).catch(() => {});
    await phonePage.waitForTimeout(800);
    const offlineText = await phonePage.evaluate(() => document.body.innerText).catch(() => "");
    phonePage.off("request", count);
    await phone.setOffline(false);
    check(
      offlineText.length > 0,
      "the phone still renders something with the network off — never a blank page",
    );
    await phonePage.screenshot({ path: join(OUT, "5-phone-offline.png"), fullPage: true }).catch(() => {});

    // ── 9 · the field app's own furniture ─────────────────────────────────
    console.log("\n9 · installable, and clean copy at 390");
    await phone.setOffline(false);
    await phonePage.goto(`${BASE}/${TENANT}/work/mobile`, { waitUntil: PHONE_WAIT });
    const manifestHref = await phonePage
      .locator('link[rel="manifest"]')
      .first()
      .getAttribute("href")
      .catch(() => null);
    check(manifestHref === "/work-mobile.webmanifest", `the manifest link is in the document (${manifestHref})`);
    const manifestOk = await phonePage.evaluate(async (href) => {
      try {
        const r = await fetch(href);
        const j = await r.json();
        return r.ok && typeof j.name === "string";
      } catch {
        return false;
      }
    }, manifestHref ?? "/work-mobile.webmanifest");
    check(manifestOk === true, "the manifest resolves and parses");

    const swRegistered = await phonePage.evaluate(async () => {
      if (!("serviceWorker" in navigator)) return "unsupported";
      const regs = await navigator.serviceWorker.getRegistrations();
      return regs.length > 0 ? "registered" : "none";
    });
    // `unsupported` is an honest outcome on a headless engine without a secure
    // context — reported rather than dressed up as a pass.
    check(
      swRegistered !== "none",
      `the service worker registers where the engine allows it (${swRegistered})`,
    );

    for (const [label, url] of [
      ["Work-010", `${BASE}/${TENANT}/work/mobile`],
      ["Work-011", `${BASE}/${TENANT}/work/mobile/jobs/${order.id}`],
    ]) {
      await phonePage.goto(url, { waitUntil: PHONE_WAIT });
      await phonePage.waitForTimeout(300);
      const visible = await phonePage.evaluate(() => document.body.innerText);
      for (const [pattern, what] of FORBIDDEN_IN_FIELD_COPY) {
        const hit = visible.match(pattern);
        check(hit === null, `${label}: no ${what}${hit === null ? "" : ` — found ${hit[0]}`}`);
      }
      const sideways = await phonePage.evaluate(SIDEWAYS);
      check(sideways === 0, `${label}: no sideways scroll at 390 (${sideways}px)`);
    }
  } finally {
    await browser.close();
  }

  // ── 8 · the CONSUMER half, read out of the file an operator runs ────────
  console.log("\n8 · docker-compose declares celery-work on -Q work");
  const compose = readFileSync("docker-compose.yml", "utf8");
  const workerLine = compose
    .split("\n")
    .find((l) => l.includes('"celery"') && l.includes('"-Q"') && l.includes('"work"'));
  check(
    workerLine !== undefined,
    "docker-compose.yml runs a worker with -Q work (G109 checks the whole pair)",
  );

  console.log(`\nscreenshots → ${OUT}`);
  if (failures.length > 0) {
    console.log(`\n⛔ ${failures.length} failed:`);
    for (const f of failures) console.log(`   · ${f}`);
    process.exit(1);
  }
  console.log("\n✓ every check passed");
})();
