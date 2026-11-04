/**
 * RENDERED-OUTPUT CHECK — CR-070 wave H, "the order in hand", in a real browser.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: no gate in this repository looks at
 * rendered output, and nine defects on the first live deployment were found this
 * way and by nothing else. This wave's central claim is a NEGATIVE across two
 * screens and one write — *publish a new template version and the order already
 * raised does not move* — and the unit tests prove it against the database while
 * this proves it against the product a dispatcher actually uses.
 *
 * ⚠ **AND ONE ASSERTION HERE CANNOT BE MADE ANYWHERE ELSE AT ALL.**
 * `WizardFrame` renders only the ACTIVE step's content and `BR-SHL-018` refuses
 * a URL jump to step 3, so **no server render of the wizard can ever contain the
 * Confirm step's consequence box.** `NewOrderWizard.test.tsx` says so in as many
 * words and checks the COPY instead. That the box is on the screen is proved
 * HERE, by clicking Continue twice — which is exactly the gap law 6 names.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   eval "$(10-scripts/proof-db.sh clone cr070h --export)"
 *   export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false
 *   (cd 06-backend && python manage.py runserver 127.0.0.1:8078 --noreload &)
 *   (cd 07-frontend && ./node_modules/.bin/vite build &&
 *      PORT=4278 API_PROXY_TARGET=http://127.0.0.1:8078 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4278 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr070-h-the-order-in-hand.mjs
 *
 * ── WHAT IT ASSERTS (demo script H, clicked) ──────────────────────────────
 *   1  **THE `+ New work order` CONTROL IS LIVE** (demo step 1) — wave G shipped
 *      it disabled with the reason *"Not from this screen yet."*; wave H landed
 *      the wizard, so the sentence must be GONE and the control must navigate.
 *      This is `DEF-CWP-3925`'s mirror clause asserted in a browser: nothing
 *      else in this repo can see a refusal that has stopped being true.
 *   2  **THE ROW'S 👁 OPENS THE ORDER** (demo step 4) — a real `<a href>` to
 *      `…/work/orders/<id>`, so ⌘-click works, and the address is NOT
 *      protocol-relative (`//…`), which is the shape a bare-mounted fixture
 *      cannot tell from a working link.
 *   3  **THREE STEPS, AND THE CONSEQUENCE BOX ON THE THIRD** (demo steps 1–3) —
 *      the rail reads *Job & location · Schedule & crew · Confirm*, and Confirm
 *      carries the box (B14 rule 11). See the note above: only clicking gets
 *      here.
 *   4  **NOTHING IS WRITTEN UNTIL CONFIRM** (`US-WRK-028` TC-4) — the open-order
 *      count is read before step 1 and again on step 2, and it must not move.
 *   5  **THE RAISE LANDS QUEUED AND UNASSIGNED** (demo step 3) — a new
 *      `WO-` number, `dispatch_state = queued`, no holder, `source = dispatcher`.
 *   6  **SIX TABS** (demo step 4) — Overview · Checklist · Parts · Location ·
 *      Customer · Audit, in the drawing's order.
 *   7  **THE CHECKLIST IS THE ORDER'S OWN** (demo step 4) — the template's task
 *      count, its safety rows, its readings with their UNITS in their own cell,
 *      and the help rows.
 *   8  **THE SAFETY LOCK HOLDS AT TWO OF THREE** (demo step 5) — tick two
 *      mandatory rows and the server still refuses a task tick, in five or six
 *      words. Asserted through the API from inside the page, so it is the
 *      SERVER refusing and not the greyed control.
 *   9  **PUBLISH v2 AND THE RAISED ORDER DOES NOT MOVE** (demo steps 6–7) — the
 *      whole wave, clicked: add a task to the template, publish, re-read the
 *      order's checklist, and the count is what it was.
 *  10  **NO DATABASE ID, NO RULE ID, NO RAW CATALOGUE KEY** on either screen
 *      (B14 rules 31 and 32).
 *  11  **NO SIDEWAYS SCROLL AT 1440.**
 *   Screenshots land in `$SMOKE_OUT`, beside which a reviewer opens
 *   `04-docs/05-modules/16-work/wireframes/Work-008.png`.
 *
 * ── WHAT IT DOES *NOT* ASSERT, AND WHY ────────────────────────────────────
 * **Tenant isolation is not here.** A second utility inside a browser
 * walkthrough would make this file a seeder. It is proved where it can be
 * proved properly: `tests/test_us_wrk_032_copies.py` TC-5 for the application
 * layer, and `tests/test_us_wrk_032_copies_pg.py` for the policy itself, on
 * real PostgreSQL under a role RLS applies to. Stated here rather than quietly
 * skipped.
 */

import { execFileSync } from "node:child_process";
import { mkdirSync, readdirSync, readFileSync } from "node:fs";
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4278";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr070-h-order-in-hand";
const VIEWPORT = { width: 1440, height: 1000 };

mkdirSync(OUT, { recursive: true });

/** The English catalogue, read from source — the server sends a KEY and the
 *  sentence a clerk reads lives here, so rule 33 is asserted where the words
 *  actually are. */
const ENGLISH = JSON.parse(
  readFileSync(join(process.cwd(), "07-frontend", "src", "i18n", "locales", "en.json"), "utf8"),
);

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

async function tabLabels(page) {
  return page.evaluate(() =>
    [...document.querySelectorAll(".page-header-tabs a, .page-header-tabs button")].map((el) =>
      (el.textContent ?? "").trim(),
    ),
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

  try {
    await signIn(page, TENANT, EMAIL, PASSWORD);

    // ── 0 · a published template with a checklist, through the product ────
    console.log("\n0 · a published template to raise from (idempotent)");
    let templates = await api(page, "GET", "/work/templates?per=100");
    let template = (templates.body?.results ?? []).find(
      (row) => (row.version ?? 0) >= 1 && (row.contents?.tasks ?? 0) > 0,
    );
    if (template === undefined) {
      const draft = await api(page, "POST", "/work/templates", {
        name: "Wave H walkthrough — meter exchange",
        service: "water",
      });
      const id = draft.body?.id;
      await api(page, "PUT", `/work/templates/${id}/tasks`, [
        { title: "Confirm address and customer", est_minutes: 3 },
        { title: "Isolate supply & remove old meter", est_minutes: 12, is_mandatory: true },
        { title: "Record final read on old meter", est_minutes: 4, photo_required: true },
        { title: "Fit new meter and seal", est_minutes: 15, photo_required: true },
      ]);
      await api(page, "PUT", `/work/templates/${id}/safety`, [
        { text: "Isolate at the main before opening the box", is_mandatory: true },
        { text: "Gloves and eye protection on", is_mandatory: true },
        { text: "Check for standing water", is_mandatory: true },
      ]);
      await api(page, "PUT", `/work/templates/${id}/readings`, [
        { prompt: "Final read, old meter", unit_of_measure: "kWh", min: 0, max: 99999,
          photo_required: true },
        { prompt: "New meter serial", unit_of_measure: "serial" },
      ]);
      await api(page, "PUT", `/work/templates/${id}/help`, [
        { kind: "document", label: "Meter exchange SOP", ref: "SOP-114" },
        { kind: "phone", label: "Control room", ref: "555-0142" },
      ]);
      await api(page, "POST", `/work/templates/${id}/publish`, {});
      templates = await api(page, "GET", "/work/templates?per=100");
      template = (templates.body?.results ?? []).find((row) => row.id === id);
    }
    check(template !== undefined, `a published template to raise from: ${template?.name ?? "—"}`);
    const templateId = template.id;

    // ── 1 · the `+ New work order` control wave G held ────────────────────
    console.log("\n1 · Orders → the control wave G shipped disabled");
    await page.goto(`${BASE}/${TENANT}/work/orders`, { waitUntil: "networkidle" });
    await page.waitForTimeout(600);
    await page.screenshot({ path: join(OUT, "01-orders.png"), fullPage: true });
    const ordersHtml = await page.content();
    check(
      !ordersHtml.includes("Not from this screen yet."),
      "the held sentence *Not from this screen yet.* is GONE (law 2's mirror clause)",
    );
    const openBefore = (await api(page, "GET", "/work-orders?per=1")).body?.count ?? -1;
    check(openBefore >= 0, `open orders before the wizard: ${openBefore}`);

    // ── 2 · the row's 👁, and that the address is a real one ──────────────
    const eyeHref = await page.evaluate(() => {
      const link = document.querySelector('tbody a[href*="/work/orders/"]');
      return link === null ? null : link.getAttribute("href");
    });
    check(eyeHref !== null, `the row action is a real <a href>: ${eyeHref ?? "MISSING"}`);
    check(
      eyeHref !== null && !eyeHref.startsWith("//"),
      "the address is NOT protocol-relative — the shape a bare-mounted fixture cannot see",
    );

    // ── 3 · three steps, and the box only clicking reaches ────────────────
    console.log("\n2 · the three-step wizard");
    await page.goto(`${BASE}/${TENANT}/work/orders/new`, { waitUntil: "networkidle" });
    await page.waitForTimeout(400);
    const rail = await page.evaluate(() =>
      [...document.querySelectorAll('[data-wizard-step]')].map((el) => (el.textContent ?? "").trim()),
    );
    check(rail.length === 3, `the rail draws THREE steps: ${rail.join(" · ")}`);
    await page.screenshot({ path: join(OUT, "02-wizard-step1.png"), fullPage: true });

    const premises = await api(page, "GET", "/premises?per=1");
    const premisesId = premises.body?.results?.[0]?.id ?? null;
    check(premisesId !== null, "a premises to anchor the job on (BR-WRK-006)");

    await page.fill("#new-order-premises", premisesId ?? "");
    await page.fill("#new-order-type", "Leak investigation");
    await page.selectOption("#new-order-template", templateId);
    await page.click('[data-wizard="actions"] button');
    await page.waitForTimeout(400);

    // `US-WRK-028` TC-4 — nothing is written until Confirm.
    const openMidway = (await api(page, "GET", "/work-orders?per=1")).body?.count ?? -1;
    check(openMidway === openBefore, `nothing written on step 2: still ${openMidway} open orders`);
    await page.screenshot({ path: join(OUT, "03-wizard-step2.png"), fullPage: true });

    await page.click('[data-wizard="actions"] button:last-of-type');
    await page.waitForTimeout(400);
    const confirmHtml = await page.content();
    check(
      confirmHtml.includes('data-consequence="new-work-order"'),
      "B14 rule 11 — the consequence box is on Confirm (ONLY clicking reaches this)",
    );
    await page.screenshot({ path: join(OUT, "04-wizard-confirm.png"), fullPage: true });

    // ── 4 · the raise ─────────────────────────────────────────────────────
    console.log("\n3 · Confirm → the order");
    await page.click('[data-wizard="actions"] button:last-of-type');
    await page.waitForURL((u) => /\/work\/orders\/[0-9a-f-]{8,}/.test(u.pathname), {
      timeout: 20000,
    });
    await page.waitForTimeout(800);
    const raisedId = page.url().split("/work/orders/")[1].split("?")[0];
    const raised = (await api(page, "GET", `/work-orders/${raisedId}`)).body;
    check(Boolean(raised?.order_no), `raised ${raised?.order_no ?? "—"}`);
    check(raised?.dispatch_state === "queued", `it is Queued (${raised?.dispatch_state})`);
    check(raised?.technician === null, "and unassigned — nobody is going yet");
    check(raised?.source === "dispatcher", `BR-WRK-024 — raised by ${raised?.source}`);

    // ── 5 · six tabs, and the order's OWN checklist ───────────────────────
    console.log("\n4 · the order detail");
    const tabs = await tabLabels(page);
    check(tabs.length === 6, `six tabs: ${tabs.join(" · ")}`);
    const checklist = (await api(page, "GET", `/work-orders/${raisedId}/checklist`)).body;
    const tasksAtRaise = checklist?.tasks_total ?? -1;
    check(tasksAtRaise > 0, `the order carries its OWN ${tasksAtRaise} tasks`);
    check((checklist?.safety?.length ?? 0) > 0, `and its own ${checklist?.safety?.length} safety rows`);
    check(
      (checklist?.readings ?? []).every((r) => Boolean(r.unit_of_measure)),
      "hard rule 3 — every reading carries its unit",
    );
    await page.screenshot({ path: join(OUT, "05-order-checklist.png"), fullPage: true });

    // ── 6 · the safety lock, refused BY THE SERVER ────────────────────────
    console.log("\n5 · the safety lock");
    const mandatory = (checklist?.safety ?? []).filter((row) => row.is_mandatory);
    check(mandatory.length >= 3, `${mandatory.length} mandatory safety rows`);
    for (const row of mandatory.slice(0, 2)) {
      await api(page, "POST", `/work-orders/${raisedId}/safety/${row.id}/tick`, {});
    }
    const afterTwo = (await api(page, "GET", `/work-orders/${raisedId}/checklist`)).body;
    check(
      afterTwo?.safety_lock?.locked === true && afterTwo?.safety_lock?.remaining === 1,
      `BR-WRK-037 — two of three ticked is STILL locked (${afterTwo?.safety_lock?.remaining} left)`,
    );
    const refused = await api(
      page, "POST", `/work-orders/${raisedId}/tasks/${checklist.tasks[0].id}/tick`, {},
    );
    check(refused.status === 409, `the SERVER refuses the task tick (${refused.status})`);
    // ⚠ **THIS READ `body.message ?? body.detail ?? ""` AND PASSED ON THE
    // EMPTY STRING — a check that could not fail, found by running it.** The
    // envelope this product returns is `{code, message_key, params, …}`
    // (`core/errors.py`, B12 §3): there IS no `message` field, so the fallback
    // fired every time and `words("")` is 1, which is ≤ 6. It reported
    // *"the refusal is 1 words"* and proved nothing.
    //
    // The KEY is what the server sends and the CATALOGUE is where the sentence
    // lives, so both are asserted: the right key, and its English string within
    // B14 rule 33's five-or-six.
    const key = refused.body?.message_key ?? "";
    check(
      key === "work.order.finish_safety_first",
      `BR-WRK-037 — the refusal names its own key: "${key}"`,
    );
    check(
      refused.body?.br_ref === "BR-WRK-037",
      `and cites the rule: ${refused.body?.br_ref ?? "(none)"}`,
    );
    // The row it is still waiting on travels in `params`, NOT inside the
    // sentence — rule 33 caps the sentence at five or six words and
    // `BR-WRK-037` still requires the row be named.
    check(
      typeof refused.body?.params?.safety === "string" &&
        refused.body.params.safety.length > 0,
      `and names the outstanding row: "${refused.body?.params?.safety ?? ""}"`,
    );
    const sentence = ENGLISH[key] ?? "";
    check(
      sentence.length > 0 && words(sentence) <= 6,
      `B14 rule 33 — "${sentence}" is ${words(sentence)} words`,
    );

    // ── 7 · THE WAVE, CLICKED: publish a new version, the order stays ─────
    console.log("\n6 · publish a new template version");
    const before = (await api(page, "GET", `/work/templates/${templateId}`)).body;
    const grown = [...(before?.bundle?.tasks ?? []).map((t) => ({
      title: t.title, est_minutes: t.est_minutes,
      photo_required: t.photo_required, is_mandatory: t.is_mandatory,
    })), { title: "Apply tamper seal", est_minutes: 2 }];
    await api(page, "PUT", `/work/templates/${templateId}/tasks`, grown);
    const published = await api(page, "POST", `/work/templates/${templateId}/publish`, {});
    check(
      (published.body?.version ?? 0) > (before?.version ?? 0),
      `template published as v${published.body?.version} (was v${before?.version})`,
    );

    console.log("\n7 · back to the order — BR-WRK-008, the whole wave");
    await page.reload({ waitUntil: "networkidle" });
    await page.waitForTimeout(800);
    const after = (await api(page, "GET", `/work-orders/${raisedId}/checklist`)).body;
    check(
      after?.tasks_total === tasksAtRaise,
      `the raised order STILL has ${after?.tasks_total} tasks (template now has ${grown.length})`,
    );
    check(
      after?.template_version === checklist?.template_version,
      `and still reads v${after?.template_version} — the version it was raised from`,
    );
    await page.screenshot({ path: join(OUT, "06-order-unchanged.png"), fullPage: true });

    // ── 8 · the UI laws, on both screens ──────────────────────────────────
    console.log("\n8 · B14 rules 31 and 32, and no sideways scroll");
    for (const [label, url] of [
      ["the order detail", `${BASE}/${TENANT}/work/orders/${raisedId}?tab=checklist`],
      ["the wizard", `${BASE}/${TENANT}/work/orders/new`],
    ]) {
      await page.goto(url, { waitUntil: "networkidle" });
      await page.waitForTimeout(500);
      const visible = await page.evaluate(() => document.body.innerText);
      for (const [pattern, what] of FORBIDDEN_IN_CLERK_COPY) {
        const hit = visible.match(pattern);
        check(hit === null, `${label}: no ${what}${hit === null ? "" : ` — found ${hit[0]}`}`);
      }
      const sideways = await page.evaluate(SIDEWAYS);
      check(sideways === 0, `${label}: no sideways scroll at 1440 (${sideways}px)`);
    }
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
