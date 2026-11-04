// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-051 (a rate per role, dated) · US-WRK-050 (a part issued
//           against a job, with no count moving) · US-WRK-053 (the frozen
//           report and its arithmetic) · US-WRK-054 (the performance tab) ·
//           US-WRK-052 (closed by ruling — nothing built)
//           Screens: Work-030, Work-025, Work-008, Work-027
// Rules:    BR-WRK-020 · BR-WRK-049 · BR-WRK-050 · BR-WRK-051 · BR-WRK-052 ·
//           BR-WRK-053 · BR-WRK-004 · hard rule 2 (money 4dp, display 2) ·
//           hard rule 5 (only the ledger posting service writes journal lines)
//           CLAUDE.md hard-won law 6
// ───────────────────────────────────────────────────────
/**
 * **Wave N's walkthrough — demo script N, clicked.**
 *
 * ── THE FIGURE THIS WHOLE WAVE IS ABOUT ───────────────────────────────────
 *
 *     hours   52 ÷ 60         = 0.8666…  →  0.87 h      (TWO decimals)
 *     labour  0.87 × 48.5000  = 42.1950  →  42.20 shown
 *     part    1   × 96.0000   = 96.0000  →  96.00 shown
 *     part    1   × 0.2200    =  0.2200  →   0.22 shown
 *     TOTAL   42.20 + 96.00 + 0.22       = 138.42
 *
 * **The total is the sum of the ROUNDED lines**, so a reader adding the printed
 * column reaches the printed total (`BR-WRK-051`). At four decimals the labour
 * line would read `42.03` and the column would not add up — which is why this
 * file asserts a LINE as well as the total. Asserting only the total would pass
 * over a build that had quietly changed how the line is rounded.
 *
 * ── WHAT MUST NOT BE ON THE SCREEN, AND BOTH ARE RULINGS ──────────────────
 *   · **NO TAX LINE** (`BR-WRK-052`). The wireframe's `149.84` is the
 *     PRE-RULING figure and appears nowhere in the product.
 *   · **NO PATH INTO FINANCE** (`BR-WRK-053`, `BR-WRK-004`; `OQ-WRK-1491`
 *     closed 2026-09-04 to option (a) — cost is captured and posted nowhere).
 *     So `journal_lines` is counted before and after and must not move.
 *
 * ⚠ **AND EVERY ONE OF THOSE IS AN ABSENCE, WHICH IS THE WEAKEST KIND OF
 * ASSERTION THERE IS.** *No tax line* passes just as happily on a report that
 * failed to render, and *`journal_lines` did not move* passes on a run where
 * nothing was accepted. So each one is PAIRED WITH A POSITIVE from the same
 * fetch: the report is asserted to carry its three lines and its total before it
 * is asserted to carry no tax; the ledger count is taken around an acceptance
 * that is separately proved to have happened. Wave L shipped exactly this
 * mistake and it is the easiest one in this repository to make.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   eval "$(10-scripts/proof-db.sh clone cr070n --export)"
 *   export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false
 *   (cd 06-backend && python manage.py runserver 127.0.0.1:8093 --noreload &)
 *   (cd 07-frontend && ./node_modules/.bin/vite build &&
 *      PORT=4293 API_PROXY_TARGET=http://127.0.0.1:8093 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4293 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr070-n-what-it-cost.mjs
 *
 * ⚠ **BUILD THE BUNDLE** — every assertion here is about rendered output.
 *
 * ⚠ **RE-RUNNABLE BY CONSTRUCTION.** Its parts carry a per-run suffix, its
 * labour rate is created only when the role has none, its template and order
 * are its own, and it asserts nothing about rows it did not write. The one
 * shared thing it touches is `journal_lines`, which it only COUNTS.
 *
 * ── WHAT IT DOES NOT CLAIM ────────────────────────────────────────────────
 * **The rendered PDF is not opened, because there is not one.** Wave N's own
 * stamp says so: *"`Work-032`'s rendered PDF and `Work-025`'s Issue-log SEGMENT
 * (the endpoint and the types ship; the segment is still disabled with its
 * reason)"*, and `work_order_reports.document_id` stays NULL until wave K's
 * `work_order_report` document kind exists. So the report's COST SECTION is
 * read from `GET /work-orders/{id}/cost` — the persisted, frozen lines the PDF
 * would print — and the demo script's step 5 is proved at that level rather
 * than pretended at the level of a document nobody has built.
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
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr070-n-what-it-cost";
const DESKTOP = { width: 1440, height: 1000 };

/** The three figures, and the fourth that must never appear. */
const HOURLY = "48.5000";
const METER_COST = "96.0000";
const SEAL_COST = "0.2200";
const LABOUR_SHOWN = "42.20";
const TOTAL_SHOWN = "138.42";
const FOUR_DECIMAL_COUNTER_CASE = "42.03"; // what 4-dp hours would give
const PRE_RULING_TOTAL = "149.84"; // the wireframe's, superseded by BR-WRK-052

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

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

/** `DEF-WRK-4051`'s only possible witness — see the wave K walkthrough's copy
 *  of this function for the full argument. Two assertions: a witness only this
 *  screen renders, and the not-built-yet placeholder ruled out BY NAME. */
async function arrivedAt(page, witness, label) {
  await page.waitForTimeout(700);
  const [present, body] = await page.evaluate((selector) => {
    return [document.querySelector(selector) !== null, document.body.innerText.slice(0, 500)];
  }, witness);
  const placeholder = body.includes("not built yet");
  check(
    present && !placeholder,
    `${label}: arrived at the screen itself` +
      (present && !placeholder
        ? ""
        : placeholder
          ? ' — fell through to "This screen is not built yet" (the registry and the mount disagree)'
          : ` — witness ${witness} is absent; page reads: ${body.replace(/\s+/g, " ").slice(0, 140)}`),
  );
  return present && !placeholder;
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: DESKTOP });
  const page = await context.newPage();

  try {
    await signIn(page, TENANT, EMAIL, PASSWORD);
    const stamp = Date.now();

    // ── 1 · Settings → Labour rates: 48.5000, and the four-decimal footnote ──
    //
    // ⚠ **THE ONE SCREEN IN THE PRODUCT THAT SHOWS MONEY AT FOUR DECIMALS**,
    // because this is where the stored value is EDITED (hard rule 2: stored to
    // 4, displayed to 2 — and the exception is stated on the screen itself
    // rather than left as a surprise).
    console.log("\n1 · Settings → Labour rates");

    const existing = await api(page, "GET", "/work/labour-rates?per=100");
    const current = (existing.body?.rows ?? []).find(
      (row) => row.role === "field_technician" && row.current === true,
    );
    if (current === undefined) {
      const made = await api(page, "POST", "/work/labour-rates", {
        role: "field_technician",
        hourly: HOURLY,
        overtime_hourly: "72.7500",
        overtime_after_hours: "8",
        effective_from: "2026-01-01",
      });
      check(made.status < 300, `a field-technician rate is set (${made.status}) ${made.status < 300 ? "" : made.text}`);
    } else {
      check(true, `a field-technician rate already exists (${current.hourly})`);
    }

    await page.goto(`${BASE}/${TENANT}/settings/reference-data/work-labour-rates`, {
      waitUntil: "networkidle",
    });
    await arrivedAt(page, 'section[aria-label="Labour rates"]', "Work-030");
    await page.waitForTimeout(900);
    const ratesText = await page.evaluate(() => document.body.innerText);
    check(
      ratesText.includes(HOURLY),
      `the rate reads ${HOURLY} — four decimals, on the one screen that shows them`,
    );
    check(
      ratesText.includes("four decimal places here"),
      "and the footnote says why this screen is the exception",
    );
    check(
      ratesText.includes("A job keeps the rate it closed at"),
      "the consequence box states what a supervisor about to change a price needs",
    );
    await page.screenshot({ path: join(OUT, "1-labour-rates.png"), fullPage: true });

    // ── 2 · Parts → issue one against a job, and NOTHING counts down ────────
    //
    // ⚠ **THE ABSENCE OF STOCK IS A RULING, NOT A GAP** — `OQ-WRK-1490`, closed
    // 2026-09-04 to option (a): *"stock control is an inventory system"*. It is
    // asserted here as the absence of a COLUMN on the register screen rather
    // than as a number that failed to change: a count that never existed cannot
    // be watched holding still, and watching one would be a check that cannot
    // fail.
    console.log("\n2 · Work → Parts — an issue is logged, and no count moves");

    const meter = await api(page, "POST", "/work/parts", {
      part_no: `MTR-E1P-${stamp}`,
      name: "Electric meter, 1-phase",
      unit_of_measure: "each",
      unit_cost: METER_COST,
    });
    const seal = await api(page, "POST", "/work/parts", {
      part_no: `SEAL-01-${stamp}`,
      name: "Meter seal",
      unit_of_measure: "each",
      unit_cost: SEAL_COST,
    });
    check(meter.status < 300 && seal.status < 300, `two parts are on the register (${meter.status}, ${seal.status})`);
    if (meter.body?.id === undefined) throw new Error(`no part: ${meter.text}`);

    const issuesBefore = await api(page, "GET", "/work/parts/issues?per=200");
    const issueCountBefore = (issuesBefore.body?.rows ?? issuesBefore.body?.results ?? []).length;
    const issued = await api(page, "POST", "/work/parts/issues", {
      part_id: meter.body.id,
      qty: "1",
      order_ref: `WO-walkthrough-${stamp}`,
      purpose: "job",
    });
    check(issued.status < 300, `one meter is issued against the job (${issued.status}) ${issued.status < 300 ? "" : issued.text}`);
    const issuesAfter = await api(page, "GET", "/work/parts/issues?per=200");
    const issueCountAfter = (issuesAfter.body?.rows ?? issuesAfter.body?.results ?? []).length;
    // The POSITIVE that gives the *nothing counted down* assertion below its
    // meaning: the log really did gain the row.
    check(
      issueCountAfter === issueCountBefore + 1,
      `the issue log gained the row (${issueCountBefore} → ${issueCountAfter})`,
    );

    const partAfter = await api(page, "GET", `/work/parts/${meter.body.id}`);
    const partKeys = Object.keys(partAfter.body ?? {});
    const stockish = partKeys.filter((k) =>
      ["on_hand", "on_hand_qty", "stock", "reorder_at", "location"].includes(k),
    );
    check(
      stockish.length === 0,
      `the register row carries NO stock field at all (${partKeys.join(", ")})`,
    );

    await page.goto(`${BASE}/${TENANT}/work/parts`, { waitUntil: "networkidle" });
    await arrivedAt(page, "[data-work-parts]", "Work-025");
    const partsText = await page.evaluate(() => document.body.innerText);
    for (const word of ["On hand", "In stock", "Reorder"]) {
      check(!partsText.includes(word), `and the screen shows no "${word}" column`);
    }
    await page.screenshot({ path: join(OUT, "2-parts.png"), fullPage: true });

    // ── 3 · a job, worked for 52 minutes, closed Passed ────────────────────
    console.log("\n3 · WO-… comes back Passed, 52 minutes on site");

    const choices = await api(page, "GET", "/work/technicians?per=100");
    const me = (choices.body?.results ?? []).find(
      (row) => (row.email ?? "").toLowerCase() === EMAIL.toLowerCase(),
    );
    check(me !== undefined, "the signed-in login is in the technician picker");
    if (me === undefined) throw new Error("no technician choice");

    // Matched BY NAME (wave L's finding) so a second run does not take the
    // create branch and collide.
    let technician = null;
    const myName = (me.full_name ?? "").trim() || me.email;
    if (me.has_profile === true) {
      const crews = await api(page, "GET", "/work/crews?per=100");
      technician = (crews.body?.results ?? []).find(
        (row) =>
          row.kind === "person" &&
          String(row.name ?? "").toLowerCase() === String(myName).toLowerCase(),
      );
    }
    if (technician === null || technician === undefined) {
      // ⚠ `role_label` MUST slugify to the rate's role code, or the close
      // stamps no rate and the report carries no labour line — which is
      // `snapshot_labour_rate_at_close`'s documented behaviour, not a failure.
      const made = await api(page, "POST", "/work/technicians", {
        user_id: me.user_id,
        role_label: "Field technician",
      });
      technician = made.body;
    }
    check(technician?.id !== undefined, "there is a technician to send");

    const draft = await api(page, "POST", "/work/templates", {
      name: `Wave N walkthrough — meter exchange ${stamp}`,
      service: "electric",
    });
    const templateId = draft.body?.id;
    check(templateId !== undefined, `a template is created (${draft.status})`);
    await api(page, "PUT", `/work/templates/${templateId}/tasks`, [
      { title: "Remove old meter", est_minutes: 12 },
    ]);
    await api(page, "PUT", `/work/templates/${templateId}/materials`, [
      { part_id: meter.body.id, planned_qty: "1" },
      { part_id: seal.body.id, planned_qty: "1" },
    ]);
    const published = await api(page, "POST", `/work/templates/${templateId}/publish`);
    check(published.status < 300, `it publishes (${published.status})`);

    const premises = await api(page, "GET", "/premises?per=1");
    const raised = await api(page, "POST", "/work-orders", {
      premises_id: (premises.body?.results ?? [])[0]?.id,
      type: "Meter exchange",
      template_id: templateId,
    });
    const orderId = raised.body?.id;
    const orderNo = raised.body?.order_no;
    check(orderId !== undefined, `the job is raised (${raised.status}) ${orderNo ?? ""}`);
    if (orderId === undefined) throw new Error(`no order: ${raised.text}`);

    await api(page, "POST", `/work-orders/${orderId}/assignments`, {
      act: "assign",
      technician_id: technician.id,
    });
    // ⚠ **THE ARRIVAL IS THE FIXTURE'S AND THERE IS ONLY ONE.** A first draft
    // posted `act: "arrive"` here as well, and that call — being the LATEST
    // arrival — is the one `snapshot_labour_rate_at_close` prices from, so the
    // span came out as the fraction of a second between it and the close and
    // the labour line read `0.00 h`. Taking the LAST arrival is deliberate (a
    // job visited twice must not bill the gap); it just means a walkthrough
    // must not add a second one.
    // ⚠ **FIFTY-TWO MINUTES, WHICH A BROWSER CANNOT WAIT FOR.** The arrival's
    // `at` is `auto_now_add` and `POST …/field-result` takes no `completed_at`
    // from its body — the staff door always stamps `now` — so the span this
    // run would otherwise produce is a fraction of a second, and asserting
    // whatever that came to would be a check that cannot fail on the one figure
    // the wave exists for. The companion fixture moves ONE timestamp backwards
    // and nothing else; every figure asserted below is still the product's own.
    const moved = execFileSync(
      "python3",
      [
        "10-scripts/render-checks/cr070-n-fixture.py",
        TENANT,
        orderId,
        "52",
      ],
      {
        encoding: "utf8",
        env: {
          ...process.env,
          DJANGO_SETTINGS_MODULE: "config.settings.local",
          DATABASE_URL:
            process.env.DATABASE_URL ??
            "postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_kn?sslmode=disable",
        },
      },
    ).trim();
    check(moved.includes("52 minutes before now"), `the crew arrived 52 minutes ago (${moved.split("\n").pop()})`);

    // Both parts are reported USED, through #75's own door.
    const checklist = await api(page, "GET", `/work-orders/${orderId}/checklist`);
    const materials = checklist.body?.materials ?? [];
    check(materials.length === 2, `the job carries its own copy of the two parts (${materials.length})`);
    for (const row of materials) {
      const used = await api(page, "PUT", `/work-orders/${orderId}/materials/${row.id}/used`, {
        used_qty: "1",
      });
      check(used.status < 300, `${row.part_no}: one used (${used.status})`);
    }

    const closed = await api(page, "POST", `/work-orders/${orderId}/field-result`, {
      outcome: "passed",
    });
    check(closed.status < 300, `the job comes back Passed (${closed.status}) ${closed.status < 300 ? "" : closed.text}`);

    // ── 4 · Accept, and the ledger does not move ───────────────────────────
    console.log("\n4 · Accept — and journal_lines is untouched (BR-WRK-004)");

    // `GET /ledger/journal-entries` — the S56 list, through `_envelope`, so the
    // figure is `count`. (`/finance/journal-lines` is not a route this product
    // has; a first draft asked for it and got `null → null`, which compares
    // equal and would have PASSED. An absence assertion that reads two nulls is
    // the purest form of the check that cannot fail.)
    const ledgerBefore = await api(page, "GET", "/ledger/journal-entries?per=1");
    const ledgerCountBefore = ledgerBefore.body?.count ?? null;

    const accepted = await api(page, "POST", `/work-orders/${orderId}/accept`);
    check(accepted.status < 300, `the acceptance is taken (${accepted.status}) ${accepted.status < 300 ? "" : accepted.text}`);

    const ledgerAfter = await api(page, "GET", "/ledger/journal-entries?per=1");
    const ledgerCountAfter = ledgerAfter.body?.count ?? null;
    // ⚠ PAIRED WITH THE POSITIVE ABOVE. *Nothing was posted* is worthless
    // without *something was accepted*, which the check above establishes.
    check(
      typeof ledgerCountBefore === "number" && ledgerCountBefore === ledgerCountAfter,
      `journal_lines did not move across a real acceptance (${ledgerCountBefore} → ${ledgerCountAfter})`,
    );

    // ── 5 · THE REPORT — three lines, and a total a reader can add up ──────
    console.log("\n5 · the report's cost section");

    const cost = await api(page, "GET", `/work-orders/${orderId}/cost`);
    check(cost.status < 300, `the cost section is served (${cost.status})`);
    const lines = cost.body?.lines ?? [];
    const total = String(cost.body?.total ?? "");
    console.log(`      lines: ${JSON.stringify(lines)}`);
    console.log(`      total: ${total}`);

    const labour = lines.find((l) => l.kind === "labour");
    check(labour !== undefined, "there is a LABOUR line on the report");
    check(
      String(labour?.qty ?? "").startsWith("0.87"),
      `52 minutes is booked as 0.87 h — TWO decimals (${labour?.qty})`,
    );
    check(
      String(labour?.rate ?? "").startsWith("48.5"),
      `priced at the rate the job closed at (${labour?.rate})`,
    );
    check(
      String(labour?.amount_display ?? "") === LABOUR_SHOWN,
      // ⚠ `amount_display` AND `amount` ARE BOTH SERVED AND THEY DIFFER ON
      // PURPOSE: `42.1950` is what is stored (hard rule 2, four decimals) and
      // `42.20` is what is PRINTED, and the total is the sum of the PRINTED
      // column (`BR-WRK-051`). A check that read `amount` would be asserting
      // the wrong one of the two and would go green on a build that had
      // stopped rounding the line at all.
      `and the line PRINTS ${LABOUR_SHOWN} while storing ${labour?.amount} (four decimals) — BR-WRK-051`,
    );
    check(
      lines.some((l) => String(l.amount_display ?? "") === "96.00"),
      "the meter line reads 96.00",
    );
    check(
      lines.some((l) => String(l.amount_display ?? "") === "0.22"),
      "the seal line reads 0.22",
    );
    check(
      total === TOTAL_SHOWN,
      `THE TOTAL IS ${TOTAL_SHOWN} (${total})`,
    );
    // ⚠ **AND IT IS THE SUM OF THE PRINTED COLUMN, ADDED UP HERE.** Asserting
    // the constant alone would pass on a total that happened to be right for
    // the wrong reason; `BR-WRK-051`'s actual claim is that a reader adding the
    // column reaches the printed total, so this file adds the column.
    const addedUp = lines
      .reduce((sum, l) => sum + Math.round(Number(l.amount_display) * 100), 0);
    check(
      addedUp === Math.round(Number(total) * 100),
      `and a reader adding the printed column reaches it (${lines
        .map((l) => l.amount_display)
        .join(" + ")} = ${(addedUp / 100).toFixed(2)})`,
    );
    // ⚠ The counter-case, asserted as an ABSENCE that has a POSITIVE beside it:
    // the labour line is 42.20 above, so 42.03 appearing anywhere would mean the
    // hours were booked at four decimals after all.
    check(
      !JSON.stringify(cost.body).includes(FOUR_DECIMAL_COUNTER_CASE),
      `and ${FOUR_DECIMAL_COUNTER_CASE} appears nowhere — hours are booked at two decimals, not four`,
    );

    // NO TAX, and the pre-ruling total nowhere — `BR-WRK-052`.
    const costText = JSON.stringify(cost.body).toLowerCase();
    check(!costText.includes("tax"), "no line, kind or description contains the word tax");
    check(
      !JSON.stringify(cost.body).includes(PRE_RULING_TOTAL),
      `and the wireframe's pre-ruling ${PRE_RULING_TOTAL} is nowhere`,
    );

    // ── 6 · Accept again — still one version ───────────────────────────────
    console.log("\n6 · Accept again — BR-WRK-050, generated ONCE");
    const reportsOnce = await api(page, "GET", `/work-orders/${orderId}/reports`);
    const versionsBefore = (reportsOnce.body?.rows ?? []).length;
    check(versionsBefore === 1, `one version exists (${versionsBefore})`);
    await api(page, "POST", `/work-orders/${orderId}/accept`);
    const reportsTwice = await api(page, "GET", `/work-orders/${orderId}/reports`);
    const versionsAfter = (reportsTwice.body?.rows ?? []).length;
    check(
      versionsAfter === versionsBefore,
      `a second Accept produced no second version (${versionsBefore} → ${versionsAfter})`,
    );
    const stillTotal = String(
      (await api(page, "GET", `/work-orders/${orderId}/cost`)).body?.total ?? "",
    );
    check(stillTotal === total, `and the total is unchanged (${stillTotal}) — frozen`);

    // ── 7 · the job's own screen shows the parts used ──────────────────────
    console.log("\n7 · Work-008's Parts tab — used of planned");
    await page.goto(`${BASE}/${TENANT}/work/orders/${orderId}?tab=parts`, {
      waitUntil: "networkidle",
    });
    await arrivedAt(page, '[data-screen="WRK-02"]', "Work-008 · Parts");
    await page.waitForTimeout(700);
    const partsTab = await page.evaluate(() => document.body.innerText);
    check(partsTab.includes(`MTR-E1P-${stamp}`), "the meter is on the job's Parts tab");
    check(!partsTab.includes("On hand"), "and there is no on-hand column here either");
    await page.screenshot({ path: join(OUT, "3-order-parts.png"), fullPage: true });

    // ── 8 · Performance — totals the field's cost, and no way into Finance ──
    console.log("\n8 · Work-027 — and no door from here into Finance");
    await page.goto(`${BASE}/${TENANT}/work/performance`, { waitUntil: "networkidle" });
    await arrivedAt(page, 'section[aria-label="Performance"]', "Work-027");
    await page.waitForTimeout(900);

    // ⚠ **SCOPED TO THE SCREEN, NOT TO THE DOCUMENT — AND THAT IS THE WHOLE
    // CARE IN THIS STEP.** The application shell's left navigation carries a
    // Finance link on EVERY page in the product, so a query over the whole
    // document finds `/brazosbend/finance` here and on the sign-in screen
    // alike. `BR-WRK-053` is about a route from THIS TAB into Finance — a
    // tile, a footnote, a button, a cell — and an assertion that fires on the
    // global nav can never pass and would eventually be deleted as noise.
    const perf = await page.evaluate(() => {
      const screen = document.querySelector('section[aria-label="Performance"]');
      const within = (sel) => Array.from(screen?.querySelectorAll(sel) ?? []);
      return {
        text: screen?.innerText ?? "",
        hrefs: within("a[href]").map((a) => a.getAttribute("href")),
        buttons: within("button").map((b) => b.textContent.trim()),
        // The nav's own Finance link, proving the query above CAN see one when
        // there is one to see — without this the two checks below would pass
        // just as happily on a page where the selector matched nothing.
        navHasFinance: Array.from(document.querySelectorAll("a[href]")).some((a) =>
          (a.getAttribute("href") ?? "").includes("/finance"),
        ),
      };
    });
    check(
      perf.navHasFinance,
      "the app shell DOES carry a Finance link — so a query that finds none below is a real absence, not a broken selector",
    );
    // The POSITIVE first: the page really rendered its own content, so the
    // absences below are absences ON a screen rather than an empty document.
    check(
      perf.text.includes("Total field cost"),
      `the performance table rendered its total row (${perf.text.slice(0, 80).replace(/\s+/g, " ")})`,
    );
    const financeLinks = perf.hrefs.filter((h) => (h ?? "").includes("/finance"));
    check(
      financeLinks.length === 0,
      `no link on this page goes into Finance (${financeLinks.join(", ") || "none"})`,
    );
    const financeButtons = perf.buttons.filter((b) => /finance|ledger|post to/i.test(b));
    check(
      financeButtons.length === 0,
      `and no button offers to post it (${financeButtons.join(", ") || "none"})`,
    );
    check(!perf.text.includes("CR-028"), "the box carries no change-request id (B14 rule 32)");
    check(
      !/\bBR-[A-Z]{3}-\d{3,5}\b/.test(perf.text),
      "and no rule id is on a clerk-facing screen (B14 rule 32)",
    );
    await page.screenshot({ path: join(OUT, "4-performance.png"), fullPage: true });
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
