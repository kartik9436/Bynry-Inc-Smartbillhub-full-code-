// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-047 (a reading with its unit; out of range is flagged and
//           accepted) · US-WRK-049 (the rule column and the file column are
//           different) · US-WRK-048 (the photograph, its key, its link) ·
//           US-WRK-036 (the signature, or the refusal)
//           Screens: Work-012 (the phone), Work-008 / Work-033 (the office)
// Rules:    BR-WRK-039 · BR-WRK-040 · BR-WRK-046 · BR-WRK-047 · BR-WRK-047a ·
//           BR-WRK-048 · hard rule 1 · hard rule 3 ·
//           CLAUDE.md hard-won law 6 (diff the running app — no gate looks at
//           rendered output) · law 2 and its mirror
// ───────────────────────────────────────────────────────
/**
 * **Wave K's walkthrough — demo script K, clicked.**
 *
 * Law 6: *"Diff the running app against `05-prototype/`. No gate looks at
 * rendered output. Nine defects were found this way and by nothing else."*
 *
 * ── THE ONE RULE THIS WAVE EXISTS TO GET RIGHT ────────────────────────────
 * `BR-WRK-039` and `BR-WRK-040` look alike and are OPPOSITES:
 *
 *   · **out of range FLAGS and never blocks** — 1,204 against a 0–999 bound is
 *     stored, shown in red, and the job still closes;
 *   · **a missing REQUIRED photograph BLOCKS** — amber, a different sentence,
 *     and the job does not close.
 *
 * A screen that renders both as one shade of *check this* teaches a technician
 * that neither matters, and the one that does is the one that stops a job
 * closing at 16:55 on a Friday. So this file asserts the two **do not share a
 * colour AND do not share a sentence**, on BOTH surfaces — which is a stronger
 * assertion than either colour alone, and is the assertion that cannot be made
 * by any test in this repository that does not render.
 *
 * ── TWO SURFACES, AND THE SECOND ONE IS WHY THIS FILE WAS WRITTEN ─────────
 * A technician records on a **390 × 844 phone**; a supervisor reads on a
 * 1440-wide desktop. Wave `K`'s `K2` commit is titled *"the three panes **on
 * the phone**"* and that is exactly what it built. `Work-033` — the same two
 * rules as the OFFICE sees them, on `Work-008`'s Checklist tab — is asserted
 * here at equal strength, because a rule that only one of the two surfaces
 * states is a rule the other surface can quietly contradict.
 *
 * ── WHAT THIS FILE DELIBERATELY DOES NOT CLAIM ───────────────────────────
 * **1 · THE FOUR-HOUR LINK IS NOT WATCHED DYING, AND IT CANNOT BE HERE.**
 * The demo script asks to *"wait past its life"*. On the backend a developer
 * and this walkthrough actually run — `DOCUMENT_STORAGE_BACKEND=filesystem` —
 * `temporary_read_url` returns a `file://` path and **says in its own docstring
 * that it does not expire, because it is not a credential**. So there is no
 * clock to move: an assertion that the link had died would either be faked or
 * would be a check that cannot fail, and this file has no business shipping
 * either. What IS asserted is the contract the server states and the guarantee
 * it actually holds: the link comes back stamped `expires_in_seconds = 14400`,
 * and `url_ttl_seconds()` **REFUSES** a longer setting rather than clamping it.
 * The expiry of the BYTES belongs to the S3 backend and is proved where it can
 * be. Stated here rather than quietly skipped — wave L's posture for the
 * savepoint, for the same reason.
 *
 * **2 · THE CROSS-TENANT FETCH IS NOT MADE FROM A SECOND UTILITY.** The seeded
 * database this runs against holds exactly ONE tenant, and standing a second
 * one up through the product's own doors would make this file a seeder rather
 * than a walkthrough (wave J's and wave L's ruling, unchanged). What IS
 * asserted is the same guarantee's observable half: an attachment that **exists
 * but belongs to another order** and an attachment id that **does not exist at
 * all** come back BYTE-IDENTICAL — which is `HR-1`'s actual claim, that the
 * difference between *not yours* and *not there* must not be observable. The
 * cross-TENANT case is `tests/test_us_wrk_048_evidence_pg.py`, on real
 * PostgreSQL under a role RLS applies to.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   eval "$(10-scripts/proof-db.sh clone cr070k --export)"
 *   export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false
 *   (cd 06-backend && python manage.py runserver 127.0.0.1:8093 --noreload &)
 *   (cd 07-frontend && ./node_modules/.bin/vite build &&
 *      PORT=4293 API_PROXY_TARGET=http://127.0.0.1:8093 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4293 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr070-k-what-came-back.mjs
 *
 * ⚠ **BUILD THE BUNDLE.** A stale `dist/` is the most expensive way to read a
 * screen: every assertion below is about rendered output, and rendered output
 * comes from the bundle rather than from the source you just edited.
 *
 * ⚠ **IT IS RE-RUNNABLE, AND THAT IS DESIGNED RATHER THAN LUCKY.** Every row it
 * needs it CREATES — its own template (named with a timestamp), its own order,
 * its own technician profile if the login has none. It asserts nothing about
 * rows it did not put there. Wave L's second run collided with a
 * one-reading-per-meter-per-day rule and wave J's technician lookup passed only
 * against an empty database; the fix for both is the same and it is this.
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4293";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr070-k-what-came-back";
const DESKTOP = { width: 1440, height: 1000 };
const PHONE = { width: 390, height: 844 };

/** Wave J's lesson: once the field app's service worker registers, the page's
 *  network state never goes quiet the way Playwright waits for, so
 *  `networkidle` hangs after a SUCCESSFUL sign-in and looks like a broken
 *  screen. The route renders on the client anyway. */
const PHONE_WAIT = "domcontentloaded";

/** THE FOUR-HOUR LINK, as a number rather than as a sentence. */
const FOUR_HOURS_IN_SECONDS = 14400;

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
  [/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/, "a database id"],
  [/\bwork\.(?:mobile|order)\.[a-z]/, "a raw catalogue key"],
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
      const text = await response.text();
      try {
        payload = JSON.parse(text);
      } catch {
        payload = null;
      }
      return { status: response.status, body: payload, text: text.slice(0, 400) };
    },
    [method, `/api/${TENANT}${path}`, body ?? null],
  );
}

/** A photograph, posted the way the phone posts one — multipart, with the key
 *  the handset minted. The bytes are a real one-pixel PNG so the server's size
 *  and content checks run against something rather than around it. */
async function postPhoto(page, orderId, { key, readingId, device, takenAt }) {
  return page.evaluate(
    async ([path, k, rid, dev, at]) => {
      const png = Uint8Array.from(
        atob(
          "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
        ),
        (c) => c.charCodeAt(0),
      );
      const form = new FormData();
      form.append("file", new Blob([png], { type: "image/png" }), "meter.png");
      form.append("idempotency_key", k);
      if (rid) form.append("reading_id", rid);
      if (dev) form.append("device", dev);
      if (at) form.append("taken_at", at);
      const response = await fetch(path, {
        method: "POST",
        body: form,
        credentials: "same-origin",
      });
      const text = await response.text();
      let body = null;
      try {
        body = JSON.parse(text);
      } catch {
        body = null;
      }
      return { status: response.status, body, text: text.slice(0, 400) };
    },
    [`/api/${TENANT}/work-orders/${orderId}/attachments`, key, readingId ?? "", device ?? "", takenAt ?? ""],
  );
}

/**
 * ⚠ **DID WE ACTUALLY ARRIVE — `DEF-WRK-4051`'s only possible witness.**
 * A registry entry proves a screen has an ENTRY; `"/:tenant" + ROUTE` is where
 * the app will actually look for it. When those disagree the door is dead and
 * every registry-based check stays green over it.
 *
 * TWO assertions, and the second is the one that catches a dead door: a screen
 * that fell through to the not-built-yet page renders no witness AND renders
 * that sentence, while a screen that is merely slow renders neither yet. So the
 * placeholder is named EXPLICITLY rather than inferred from an absence — *this
 * is the wrong screen* and *this screen has not painted yet* are different
 * failures and a check that conflates them wastes an hour.
 */
async function arrivedAt(page, witness, label) {
  await page.waitForTimeout(600);
  const [present, body] = await page.evaluate((selector) => {
    return [document.querySelector(selector) !== null, document.body.innerText.slice(0, 400)];
  }, witness);
  const placeholder = body.includes("not built yet");
  check(
    present && !placeholder,
    `${label}: arrived at the screen itself` +
      (present && !placeholder
        ? ""
        : placeholder
          ? ' — fell through to "This screen is not built yet" (DEF-WRK-4051\'s class: the registry and the mount disagree)'
          : ` — witness ${witness} is absent; page reads: ${body.replace(/\s+/g, " ").slice(0, 140)}`),
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

    // ── 0 · the fixture, built through the product's own doors ────────────
    //
    // FOUR readings, chosen so that all three of the wave's states exist on one
    // job at once and the footer has a non-trivial number to state:
    //
    //   1 Final read on old meter   kWh  0–99999  required  photo required
    //   2 Opening read on new meter kWh  0–999    required  photo required  ← 1,204 is OUT OF RANGE
    //   3 New meter serial          serial        optional  no photograph
    //   4 Voltage at socket         V    110–125  required  photo required  ← never taken → BLOCKS
    //
    // Values on 1, 2, 3 and photographs on 1, 2 give the footer its
    // *3 of 4 readings captured · 2 of 3 required photographs*.
    console.log("\n0 · a technician, a four-reading template, and one job on it");

    const choices = await api(deskPage, "GET", "/work/technicians?per=100");
    const me = (choices.body?.results ?? []).find(
      (row) => (row.email ?? "").toLowerCase() === EMAIL.toLowerCase(),
    );
    check(me !== undefined, `the signed-in login is in the technician picker (${EMAIL})`);
    if (me === undefined) throw new Error("cannot find the signed-in login among staff choices");

    // ⚠ **MATCHED BY NAME, NOT BY `user_id`** — wave L's finding, and it is the
    // reason this file can be run twice. `GET /work/crews` is `Work-023`'s one
    // table and a person row deliberately carries `name` and `slug` and NO
    // `user_id`, because B14 rule 31 makes the name the visible value. A lookup
    // keyed on `user_id` can never match, so it takes the create branch every
    // time and collides the moment the profile already exists.
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

    const stamp = Date.now();
    const draft = await api(deskPage, "POST", "/work/templates", {
      name: `Wave K walkthrough — meter exchange ${stamp}`,
      service: "electric",
    });
    const templateId = draft.body?.id;
    check(templateId !== undefined, `a draft template is created (${draft.status})`);
    if (templateId === undefined) throw new Error(`no template: ${draft.text}`);

    await api(deskPage, "PUT", `/work/templates/${templateId}/safety`, [
      { text: "Isolate at the service head before removal", is_mandatory: true },
    ]);
    await api(deskPage, "PUT", `/work/templates/${templateId}/tasks`, [
      { title: "Confirm address and customer", est_minutes: 3 },
      { title: "Remove old meter", est_minutes: 12 },
    ]);
    const readingsPut = await api(deskPage, "PUT", `/work/templates/${templateId}/readings`, [
      {
        prompt: "Final read on old meter",
        unit_of_measure: "kWh",
        min: 0,
        max: 99999,
        required: true,
        photo_required: true,
      },
      {
        // ⚠ THE BOUND IS 0–999 ON PURPOSE. 1,204 must be OUTSIDE it, or the
        // whole point of the wave is untested and this file passes over it.
        prompt: "Opening read on new meter",
        unit_of_measure: "kWh",
        min: 0,
        max: 999,
        required: true,
        photo_required: true,
      },
      { prompt: "New meter serial", unit_of_measure: "serial", required: false },
      {
        prompt: "Voltage at socket",
        unit_of_measure: "V",
        min: 110,
        max: 125,
        required: true,
        photo_required: true,
      },
    ]);
    check(readingsPut.status < 300, `four readings on the template (${readingsPut.status})`);
    const published = await api(deskPage, "POST", `/work/templates/${templateId}/publish`);
    check(published.status < 300, `the template publishes (${published.status})`);

    const premises = await api(deskPage, "GET", "/premises?per=1");
    const premisesId = (premises.body?.results ?? [])[0]?.id;
    check(premisesId !== undefined, "there is a premises to raise an order on");

    const raised = await api(deskPage, "POST", "/work-orders", {
      premises_id: premisesId,
      type: "Meter exchange",
      template_id: templateId,
    });
    check(raised.status < 300, `the job is raised (${raised.status})`);
    if (raised.body?.id === undefined) throw new Error(`no order raised: ${raised.text}`);
    const orderId = raised.body.id;
    const orderNo = raised.body.order_no;
    check(
      typeof orderNo === "string" && orderNo.length > 0,
      `the job has a NUMBER a person can read (${orderNo}) — B14 rule 31`,
    );
    // ⚠ **TODAY, AND THAT IS NOT COSMETIC.** `Work-010` fetches
    // `GET /work/mobile/today` and calls `syncJob` for each job it names; a job
    // scheduled for another date is never on that list, so its bundle is never
    // written, and `Work-012` opens on an EMPTY readings pane — which reads
    // exactly like a broken screen. The first draft of this file dated the
    // window to 15 March and spent a run finding that out.
    const todayAt0915 = `${new Date().toISOString().slice(0, 10)}T09:15:00Z`;
    await api(deskPage, "POST", `/work-orders/${orderId}/assignments`, {
      act: "assign",
      technician_id: technician.id,
      window_start: todayAt0915,
    });

    const checklist0 = await api(deskPage, "GET", `/work-orders/${orderId}/checklist`);
    const rows0 = checklist0.body?.readings ?? [];
    check(rows0.length === 4, `the order carries its own copy of the four readings (${rows0.length})`);
    const opening = rows0.find((r) => r.prompt === "Opening read on new meter");
    const finalRead = rows0.find((r) => r.prompt === "Final read on old meter");
    const serial = rows0.find((r) => r.prompt === "New meter serial");
    const voltage = rows0.find((r) => r.prompt === "Voltage at socket");
    check(
      opening !== undefined && voltage !== undefined,
      "both readings the rule turns on are on the job",
    );
    if (opening === undefined || voltage === undefined) throw new Error("fixture readings missing");
    check(
      `${opening.min_value}`.startsWith("0") && `${opening.max_value}`.startsWith("999"),
      `the opening read is bounded 0–999, so 1,204 is genuinely outside it (${opening.min_value}–${opening.max_value})`,
    );
    check(
      voltage.photo_required === true && voltage.photo_attachment_id === null,
      "the voltage row asks for a photograph and has none — the BLOCKING case exists",
    );

    // ── 1 · the phone: the day is synced, then 1,204 is TYPED ─────────────
    //
    // ⚠ **THE DAY IS OPENED FIRST, AND IT IS A STEP RATHER THAN A COURTESY.**
    // `Work-012` renders from the OFFLINE BUNDLE (`readJob`), which is written
    // by `Work-010`'s sync and by nothing else — *"the bundle was written at
    // sync; opening a job READS and never fetches"*, which is what makes
    // `US-WRK-042` TC-1's *zero network requests during the tap* true. A
    // walkthrough that jumped straight to the job would find an empty pane and
    // report a broken screen over a correctly-designed one.
    console.log("\n1 · on the phone — the day syncs, then 1,204 is typed in");

    await phonePage.goto(`${BASE}/${TENANT}/work/mobile`, { waitUntil: PHONE_WAIT });
    await arrivedAt(phonePage, '[data-testid="offline-marker"]', "Work-010");
    await phonePage.waitForTimeout(2500);
    const dayText = await phonePage.evaluate(() => document.body.innerText);
    check(
      dayText.includes(orderNo),
      `the job is on the technician's day (${orderNo})`,
    );

    await phonePage.goto(`${BASE}/${TENANT}/work/mobile/jobs/${orderId}/readings`, {
      waitUntil: PHONE_WAIT,
    });
    await phonePage.waitForTimeout(1500);
    await arrivedAt(phonePage, "[data-reading-id]", "Work-012 · Readings");

    // ⚠ **TYPED AND BLURRED, NOT PUT.** The value goes in through the input a
    // technician actually touches, so `saveValue` runs — which is what carries
    // the UNIT with the number (hard rule 3). Driving the API instead would
    // prove the server and leave the screen untested, which is the half this
    // whole file exists for.
    async function typeReading(prompt, value) {
      const field = phonePage.locator(`input[aria-label="${prompt}"]`);
      await field.fill(value);
      await field.blur();
      await phonePage.waitForTimeout(900);
    }
    await typeReading("Final read on old meter", "48221");
    await typeReading("Opening read on new meter", "1204");
    await typeReading("New meter serial", "0");

    // ⚠ **THE CAMERA IS DRIVEN TOO** — `attach` compresses the file on the
    // handset before it leaves (`BR-WRK-047`, the PO's 100 KB ruling), so a
    // walkthrough that posted multipart itself would skip `compressPhoto`
    // entirely and prove nothing about the one step that ruling created.
    const ONE_PIXEL_PNG = Buffer.from(
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
      "base64",
    );
    async function photograph(prompt) {
      const row = phonePage.locator(`li[data-reading-id]:has(input[aria-label="${prompt}"])`);
      await row.locator('input[type="file"]').setInputFiles({
        name: "meter.png",
        mimeType: "image/png",
        buffer: ONE_PIXEL_PNG,
      });
      await phonePage.waitForTimeout(1500);
    }
    await photograph("Final read on old meter");
    await photograph("Opening read on new meter");

    // What the SERVER made of all that — read back rather than assumed.
    const afterTyping = await api(deskPage, "GET", `/work-orders/${orderId}/checklist`);
    const openingNow = (afterTyping.body?.readings ?? []).find(
      (r) => r.prompt === "Opening read on new meter",
    );
    check(
      String(openingNow?.value ?? "").startsWith("1204"),
      `1,204 was ACCEPTED and stored, not refused (${openingNow?.value}) — BR-WRK-039`,
    );
    // ⚠ SERVER-DERIVED, never taken from the request. A phone that sent
    // `in_range: true` must not be believed.
    check(
      openingNow?.in_range === false,
      `and the server flagged it out of range on its own (in_range=${openingNow?.in_range})`,
    );
    check(
      openingNow?.photo_attachment_id !== null && openingNow?.photo_attachment_id !== undefined,
      "the photograph taken on the row is attached to that row",
    );
    const attachmentId = openingNow?.photo_attachment_id;

    // ⚠ **THE POSITIVE THAT THE IDEMPOTENCY ASSERTION NEEDS.** *The same key
    // twice writes one row* passes just as happily when the first write never
    // happened, so the count is taken BEFORE and AFTER and the first delivery
    // is asserted to have ADDED one.
    const listAfterCamera = await api(deskPage, "GET", `/work-orders/${orderId}/attachments`);
    const cameraCount = (listAfterCamera.body ?? []).length;
    check(cameraCount === 2, `the two photographs the camera took are on the job (${cameraCount})`);

    // ⚠ **THE ZERO IS PAIRED WITH A POSITIVE, WHICH IS THE WHOLE CARE HERE.**
    // *The same key twice writes one row* passes just as happily when the FIRST
    // write never happened. So the first delivery is asserted to have ADDED
    // one, and only then is the retry asserted to have added none.
    const firstSend = await postPhoto(deskPage, orderId, {
      key: `k5-retry-${stamp}`,
      device: "D. Ortiz",
      takenAt: "2026-03-15T16:40:00Z",
    });
    check(firstSend.status < 300, `a third photograph is delivered (${firstSend.status})`);
    check(firstSend.body?.duplicate === false, "and the server says it WROTE it");
    const afterFirst = (
      (await api(deskPage, "GET", `/work-orders/${orderId}/attachments`)).body ?? []
    ).length;
    check(
      afterFirst === cameraCount + 1,
      `it really added one (${cameraCount} → ${afterFirst}) — the positive the zero below needs`,
    );
    const again = await postPhoto(deskPage, orderId, {
      key: `k5-retry-${stamp}`,
      device: "D. Ortiz",
      takenAt: "2026-03-15T16:40:00Z",
    });
    check(again.body?.duplicate === true, "the same key comes back marked as one it already had");
    const afterRetry = (
      (await api(deskPage, "GET", `/work-orders/${orderId}/attachments`)).body ?? []
    ).length;
    check(
      afterRetry === afterFirst,
      `and the re-send added NOTHING (${afterFirst} → ${afterRetry}) — BR-WRK-047`,
    );

    // ── 2 · the phone states the two rules apart ──────────────────────────
    console.log("\n2 · on the phone — red that does not block, amber that does");
    await phonePage.reload({ waitUntil: PHONE_WAIT });
    await phonePage.waitForTimeout(1200);

    const phoneFlags = await phonePage.evaluate(() => {
      const pick = (sel) => {
        const el = document.querySelector(sel);
        return el ? { text: el.textContent.trim(), cls: el.className } : null;
      };
      return {
        outOfRange: pick('[data-flag="out-of-range"]'),
        missingPhoto: pick('[data-flag="missing-photo"]'),
        consequence: pick("[data-consequence]"),
        body: document.body.innerText,
      };
    });
    check(phoneFlags.outOfRange !== null, "the phone shows the out-of-range line");
    check(phoneFlags.missingPhoto !== null, "the phone shows the missing-photograph line");
    check(
      phoneFlags.outOfRange !== null &&
        phoneFlags.missingPhoto !== null &&
        phoneFlags.outOfRange.text !== phoneFlags.missingPhoto.text,
      `the two do not share a SENTENCE ("${phoneFlags.outOfRange?.text}" vs "${phoneFlags.missingPhoto?.text}")`,
    );
    check(
      phoneFlags.outOfRange !== null &&
        phoneFlags.missingPhoto !== null &&
        phoneFlags.outOfRange.cls !== phoneFlags.missingPhoto.cls,
      "and they do not share a COLOUR — different classes, not two shades of one warning",
    );
    check(
      (phoneFlags.consequence?.text ?? "").includes("out of range never blocks"),
      `the consequence line spells out which is which ("${phoneFlags.consequence?.text ?? "absent"}")`,
    );
    check(
      phoneFlags.body.includes("3 of 4") && phoneFlags.body.includes("2 of 3"),
      "the footer counts both: 3 of 4 readings captured, 2 of 3 required photographs",
    );
    await phonePage.screenshot({ path: join(OUT, "1-phone-readings.png"), fullPage: true });

    // ── 3 · the server's own verdict, which both surfaces must obey ───────
    console.log("\n3 · close-readiness — flagged is not blocking, and the job cannot close");
    const ready = await api(deskPage, "GET", `/work-orders/${orderId}/close-readiness`);
    const verdict = ready.body ?? {};
    check(verdict.can_close === false, `the job CANNOT close (can_close=${verdict.can_close})`);
    check(
      (verdict.blocking ?? []).some(
        (b) => b.kind === "missing_required_photo" && b.prompt === "Voltage at socket",
      ),
      "and what blocks it is the missing REQUIRED photograph, named",
    );
    check(
      (verdict.flagged ?? []).some((f) => f.kind === "out_of_range" && f.prompt === "Opening read on new meter"),
      "1,204 is on the FLAGGED list",
    );
    check(
      !(verdict.blocking ?? []).some((b) => b.kind === "out_of_range"),
      "and it is NOT on the blocking list — out of range never blocks, on the server too",
    );
    check(
      verdict.readings_captured === 3 && verdict.readings_total === 4,
      `3 of 4 readings captured (${verdict.readings_captured} of ${verdict.readings_total})`,
    );
    check(
      verdict.required_photos_taken === 2 && verdict.required_photos_total === 3,
      `2 of 3 required photographs (${verdict.required_photos_taken} of ${verdict.required_photos_total})`,
    );

    // ── 4 · THE OFFICE — Work-033 on Work-008's Checklist tab ─────────────
    //
    // The supervisor's half of the same two rules. Everything asserted here is
    // already SERVED: `in_range` and `photo_attachment_id` are on every row of
    // `GET /work-orders/{id}/checklist`, and `close-readiness` publishes the
    // two lists and the two counts.
    console.log("\n4 · in the office — Work-008's Checklist tab (Work-033)");
    // ⚠ **BY THE ID THE ORDERS LIST ACTUALLY LINKS WITH.** The route parameter
    // is named `:orderNo` and `OrdersPage` feeds it `row.id` — a uuid — so the
    // three queries on this screen address the API by uuid. Navigating with the
    // order NUMBER 404s all three and leaves a rendered shell with no data,
    // which is indistinguishable from a broken screen and cost this file a run.
    // The name lies; the caller is the truth. (Reported as DEF-WRK-4115.)
    await deskPage.goto(`${BASE}/${TENANT}/work/orders/${orderId}?tab=checklist`, {
      waitUntil: "networkidle",
    });
    await arrivedAt(deskPage, '[data-screen="WRK-02"]', "Work-008");
    await deskPage.waitForTimeout(800);

    const office = await deskPage.evaluate(() => {
      const rowFor = (prompt) => {
        for (const tr of document.querySelectorAll("tr")) {
          if (tr.textContent.includes(prompt)) return tr;
        }
        return null;
      };
      const opening = rowFor("Opening read on new meter");
      const voltage = rowFor("Voltage at socket");
      const flagEl = opening?.querySelector('[data-flag="out-of-range"]') ?? null;
      const blockEl = voltage?.querySelector('[data-flag="missing-photo"]') ?? null;
      return {
        openingText: opening ? opening.innerText.replace(/\s+/g, " ").trim() : null,
        voltageText: voltage ? voltage.innerText.replace(/\s+/g, " ").trim() : null,
        flag: flagEl ? { text: flagEl.textContent.trim(), cls: flagEl.className } : null,
        block: blockEl ? { text: blockEl.textContent.trim(), cls: blockEl.className } : null,
        thumbs: document.querySelectorAll("[data-thumbnail]").length,
        body: document.body.innerText,
      };
    });

    check(office.openingText !== null, "the opening-read row is on the supervisor's screen");
    check(
      (office.openingText ?? "").includes("1,204") || (office.openingText ?? "").includes("1204"),
      `and it shows the value the technician typed (${office.openingText ?? "row absent"})`,
    );
    check(
      office.flag !== null,
      `the row says OUT OF RANGE to the supervisor${office.flag ? "" : " — no out-of-range element on Work-033"}`,
    );
    check(
      (office.voltageText ?? "").includes("not taken"),
      `the voltage row reads *not taken* (${office.voltageText ?? "row absent"})`,
    );
    check(
      office.block !== null,
      `and says the job CANNOT CLOSE${office.block ? "" : " — no blocking element on Work-033"}`,
    );
    check(
      office.flag !== null && office.block !== null && office.flag.text !== office.block.text,
      "the office states the two rules in DIFFERENT SENTENCES, as the phone does",
    );
    check(
      office.flag !== null && office.block !== null && office.flag.cls !== office.block.cls,
      "and in DIFFERENT COLOURS",
    );
    check(
      office.thumbs >= 2,
      `each captured reading carries a thumbnail (${office.thumbs} found, 2 expected)`,
    );
    check(
      (office.body ?? "").includes("3 of 4") && (office.body ?? "").includes("2 of 3"),
      "and the footer states the same two counts the phone states",
    );
    await deskPage.screenshot({ path: join(OUT, "2-office-checklist.png"), fullPage: true });

    // ── 5 · the thumbnail opens to WHO, WHEN and WHICH PHONE ──────────────
    console.log("\n5 · the thumbnail opens — who took it, when, on which phone");
    const opened = await deskPage.evaluate(() => {
      const thumb = document.querySelector("[data-thumbnail]");
      if (!thumb) return null;
      (thumb.querySelector("button") ?? thumb).click();
      return true;
    });
    check(opened === true, "there is a thumbnail to open");
    if (opened === true) {
      await deskPage.waitForTimeout(700);
      const lightbox = await deskPage.evaluate(() => {
        const box = document.querySelector("[data-lightbox]");
        return box ? box.innerText.replace(/\s+/g, " ").trim() : null;
      });
      check(lightbox !== null, "it opens a lightbox");
      // ⚠ **THE PERSON, NOT THE DEMO SCRIPT'S ILLUSTRATIVE NAME.** Demo script
      // K says the thumbnail opens to *IMG-8842 · D. Ortiz · 16:02*; D. Ortiz
      // is that script's technician and this run's is whoever signed in. What
      // is asserted is that a PERSON is named at all — which is the fact
      // `DEF-WRK-4114` found missing: `_attachment_dict` published `device`,
      // which no client sends, and withheld `added_by`, which every row has.
      check(
        (lightbox ?? "").includes(myName),
        `and the lightbox names WHO took it — "${myName}" (${lightbox ?? "absent"})`,
      );
      check(
        /\d{4}-\d{2}-\d{2}/.test(lightbox ?? ""),
        "and WHEN it was taken",
      );
      await deskPage.screenshot({ path: join(OUT, "3-thumbnail.png"), fullPage: true });
    }

    // ── 6 · the customer signs, and the Customer tab shows it ─────────────
    console.log("\n6 · S. Miller signs, and the office sees the signature");
    const signed = await phonePage.evaluate(
      async ([path]) => {
        const png = Uint8Array.from(
          atob(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
          ),
          (c) => c.charCodeAt(0),
        );
        const form = new FormData();
        form.append("file", new Blob([png], { type: "image/png" }), "signature.png");
        form.append("printed_name", "S. MILLER");
        const response = await fetch(path, { method: "POST", body: form, credentials: "same-origin" });
        const text = await response.text();
        let body = null;
        try {
          body = JSON.parse(text);
        } catch {
          body = null;
        }
        return { status: response.status, body, text: text.slice(0, 300) };
      },
      [`/api/${TENANT}/work-orders/${orderId}/signature`],
    );
    check(signed.status < 300, `the signature is captured (${signed.status}) ${signed.status < 300 ? "" : signed.text}`);
    check(signed.body?.refused === false || signed.body?.refused === undefined, "it is a signature and not a refusal");

    await deskPage.goto(`${BASE}/${TENANT}/work/orders/${orderId}?tab=customer`, {
      waitUntil: "networkidle",
    });
    await arrivedAt(deskPage, '[data-screen="WRK-02"]', "Work-008 · Customer");
    await deskPage.waitForTimeout(700);
    const customerTab = await deskPage.evaluate(() => document.body.innerText);
    check(
      customerTab.includes("S. MILLER") || customerTab.includes("S. Miller"),
      "the Customer tab shows who signed",
    );
    await deskPage.screenshot({ path: join(OUT, "4-customer-tab.png"), fullPage: true });

    // ── 7 · the photograph's link, and what this file can honestly say ────
    console.log("\n7 · the link — four hours, and a setting the server refuses to lengthen");
    const link = await api(deskPage, "GET", `/work-orders/${orderId}/attachments/${attachmentId}`);
    check(link.status < 300, `a link is minted for the photograph (${link.status})`);
    check(
      link.body?.expires_in_seconds === FOUR_HOURS_IN_SECONDS,
      `and it is stamped with a four-hour life (${link.body?.expires_in_seconds}s)`,
    );
    check(
      typeof link.body?.url === "string" && link.body.url.length > 0,
      "the link carries a url",
    );
    // ⚠ **NOT WATCHED DYING — see this file's header.** On the filesystem
    // backend the url is a `file://` path that does not expire, so an assertion
    // that it had gone would be faked. What is asserted instead is the SHAPE of
    // the guarantee: the life is the four hours the ruling caps it at, and the
    // number is read off the server rather than restated here.
    check(
      link.body?.expires_in_seconds <= FOUR_HOURS_IN_SECONDS,
      "the server never mints a link that outlives the cap",
    );

    // ── 8 · not yours and not there are the same answer ───────────────────
    console.log("\n8 · HR-1 — *not yours* and *not there* must be indistinguishable");
    const otherOrder = await api(deskPage, "POST", "/work-orders", {
      premises_id: premisesId,
      type: "Meter exchange",
      template_id: templateId,
    });
    const otherId = otherOrder.body?.id;
    check(otherId !== undefined, "a second job exists to ask the wrong question of");
    const notMine = await api(
      deskPage,
      "GET",
      `/work-orders/${otherId}/attachments/${attachmentId}`,
    );
    const notThere = await api(
      deskPage,
      "GET",
      `/work-orders/${otherId}/attachments/00000000-0000-7000-8000-000000000000`,
    );
    check(notMine.status === 404, `a photograph of ANOTHER job is 404 (${notMine.status})`);
    check(notThere.status === 404, `a photograph that does not exist is 404 (${notThere.status})`);
    // The bodies carry a trace id that differs per request, so they are compared
    // with that field removed — everything a caller could learn FROM must match.
    const strip = (body) => {
      const copy = JSON.parse(JSON.stringify(body ?? {}));
      delete copy.trace_id;
      if (copy.error) delete copy.error.trace_id;
      return JSON.stringify(copy);
    };
    check(
      strip(notMine.body) === strip(notThere.body),
      `and the two answers are IDENTICAL — nothing distinguishes *not yours* from *not there*\n       ${strip(notMine.body)}\n       ${strip(notThere.body)}`,
    );

    // ── 9 · what a technician must never be shown ─────────────────────────
    console.log("\n9 · B14 rules 31 and 32 on the phone, and no sideways scroll at 390");
    for (const [label, url] of [
      ["Work-012 · readings", `${BASE}/${TENANT}/work/mobile/jobs/${orderId}/readings`],
      ["Work-012 · signature", `${BASE}/${TENANT}/work/mobile/jobs/${orderId}/signature`],
    ]) {
      await phonePage.goto(url, { waitUntil: PHONE_WAIT });
      await phonePage.waitForTimeout(600);
      const visible = await phonePage.evaluate(() => document.body.innerText);
      for (const [pattern, what] of FORBIDDEN_IN_FIELD_COPY) {
        const hit = visible.match(pattern);
        check(hit === null, `${label}: no ${what}${hit === null ? "" : ` — found ${hit[0]}`}`);
      }
      const sideways = await phonePage.evaluate(SIDEWAYS);
      check(sideways === 0, `${label}: no sideways scroll at 390 (${sideways}px)`);
    }
    await phonePage.screenshot({ path: join(OUT, "5-phone-signature.png"), fullPage: true });
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
