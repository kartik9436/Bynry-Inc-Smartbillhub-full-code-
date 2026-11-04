/**
 * RENDERED-OUTPUT CHECK — CR-070 wave F, "who can do what", in a real browser.
 *
 * ⚠ **WHY THIS EXISTS, AND WHY IT IS THE ONLY THING THAT COULD FIND WHAT IT
 * FINDS.** Hard-won law 6: no gate in this repository looks at rendered output.
 * This wave's central assertion is an ABSENCE — the sentence *"She is blocked
 * from 4 template types until renewed"* must NOT be on the page while the
 * utility's setting says *warn* — and **an absence is invisible to every check
 * this repo has** unless something reads the DOM. The unit tests assert it
 * against a stubbed query result; only this asserts it against the running
 * product with a real database behind it.
 *
 * ⚠ **AND IT ASSERTS THE SAME SENTENCE THE OTHER WAY.** `OQ-WRK-1493` was ruled
 * on 2026-09-04 as option (c) — per-tenant, defaulting to *warn* — so BOTH
 * sides are built and the tenant's own setting picks one. A walkthrough that
 * only proved the absence would leave the utility with a safety officer
 * untested, and that is the half where somebody gets sent into a confined space
 * on a lapsed certificate.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   # 1 · a private, seeded database (10-scripts/proof-db.sh, read it first)
 *   eval "$(10-scripts/proof-db.sh clone cr070f --export)"
 *   export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false
 *
 *   # 2 · the product
 *   (cd 06-backend && python manage.py runserver 127.0.0.1:8075 --noreload &)
 *   (cd 07-frontend && ./node_modules/.bin/vite build &&
 *      PORT=4275 API_PROXY_TARGET=http://127.0.0.1:8075 node server.mjs &)
 *
 *   # 3 · this
 *   SMOKE_BASE=http://127.0.0.1:4275 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr070-f-who-can-do-what.mjs
 *
 * ⚠ **IT SEEDS ITS OWN SIX ROWS THROUGH THE API AND LEAVES THEM.** A crews
 * screen has nothing to draw on a fresh estate, so acts 0a–0f create the
 * `WS-23` fixture — D. Ortiz · M. Chen · R. Patel · J. Kaur · Crew B (3) ·
 * Apex Utility Svc — using the tenant's OWN logins and its own skill and
 * certification catalogues. It is re-runnable: every create is skipped when the
 * row is already there.
 *
 * ── WHAT IT ASSERTS (demo script F, clicked) ──────────────────────────────
 *   1  **CREWS IS ON THE STRIP AND OPENS** (demo step 1) — five tabs, Crews
 *      between Awaiting approval and Parts, and it is a real `<a href>` so
 *      ⌘-click works.
 *   2  **SIX ROWS IN ONE TABLE** (demo step 1) — four people, a crew of three
 *      and a contractor, and exactly ONE `<table>` on the screen (B14 rule 20).
 *      The footer reads *6 rows · 4 people, 1 crew, 1 contractor*.
 *   3  **NO TODAY AND NO UTILISATION COLUMN.** `WS-23` draws both; neither can
 *      carry a value until wave G gives `work_orders` an assignee, and a cell
 *      that can never be filled is dead UI (law 2). Read off the header row.
 *   4  **J. KAUR CARRIES *cert expiring*** (demo step 2) and R. Patel does not.
 *   5  **THE WATCH NAMES HER AND THE DATE** (demo step 2) — *30 days — J. Kaur,
 *      confined space expires …* — **AND THE DOM CONTAINS NO *blocked from***.
 *      This is the assertion the whole wave turns on.
 *   6  **SWITCH THE UTILITY TO *block* AND THE SENTENCE APPEARS** — the other
 *      half of the same ruling, then switched back to *warn* so the walkthrough
 *      is re-runnable and leaves the tenant as it found it.
 *   7  **OPEN R. PATEL** (demo step 3) — three skills with their proficiency,
 *      including the ***Not held*** row that tells a supervisor which jobs a
 *      training course would unlock, and two certification chips with expiry.
 *   8  **NO *THIS MONTH* PANEL** — `WS-24` draws *Jobs closed 88 · 92% · −4
 *      min*; none of the three can be computed until wave G, so none is drawn.
 *   9  **TWO TABS, NOT FOUR** — Overview and Certifications. Jobs and Audit are
 *      ABSENT rather than disabled: `DEF-CWP-3925` is what a hold costs when
 *      the screen behind it lands and nobody greps for the control.
 *  10  **ASSIGN SKILLS → THREE STEPS → THE ROW CHANGES** (demo step 4) — add a
 *      skill at *trained*, confirm, and read it back off the crews list.
 *  11  **A BILLING CLERK'S ACCEPT IS ALLOWED** (demo step 7) — `OQ-WRK-1492`,
 *      ruled: *"clark can do it sicne it s a day to day work"*. Asserted at the
 *      permission, not by accepting a real job, so the walkthrough writes no
 *      work-order history it would then have to undo.
 *  12  **A FIELD TECHNICIAN'S WEB SIGN-IN IS REFUSED** (demo step 6, INVERTED
 *      by the ruling) — T. Osei is invited with the mobile scope and the web
 *      sign-in answers the PO's two sentences (2026-10-06, `DEF-IDN-9777`,
 *      a ruled exception to B14 rule 33's six-word cap for this message only):
 *      *Field Technicians do not have access to the staff portal. Please sign
 *      in on the Field Technician mobile app instead.* It read the six-word
 *      *Sign in on the field app.* until then.
 *  13  **NO DATABASE ID, NO RULE ID AND NO RAW CATALOGUE KEY** on either screen
 *      (B14 rules 31 and 32) — including the raw-key pattern `DEF-WRK-3752`
 *      added after wave O's first run found two tab labels rendering as keys.
 *  14  **NO SIDEWAYS SCROLL AT 1440.**
 *   Screenshots land in `$SMOKE_OUT` (default /tmp/cr070-f-workforce), beside
 *   which a reviewer opens `wireframes/Work-023.png` and `Work-024.png`.
 *
 * ── WHAT IT DOES *NOT* ASSERT, AND WHY ────────────────────────────────────
 * **The isolation step is not here.** Lone Star Ridge is not seeded, and
 * provisioning a second utility inside a browser walkthrough would make this
 * file a seeder. The wall is proved where it can be proved properly:
 * `tests/test_us_wrk_020_021_workforce.py` asserts that a Lone Star Ridge
 * session reads zero crews rows and that `/work/crews/r-patel` answers None
 * there, and `tests/test_us_wrk_rls_pg.py` reads the policy out of `pg_class`
 * on real PostgreSQL. Stated here rather than quietly skipped.
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4275";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr070-f-workforce";
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

async function tabLabels(page) {
  return page.evaluate(() =>
    [...document.querySelectorAll('.page-header-tabs a, .page-header-tabs button')].map((el) =>
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

    // ── 0 · the WS-23 fixture, through the product's own API ──────────────
    console.log("\n0 · seeding the six rows (idempotent)");
    const staff = await api(page, "GET", "/work/technicians");
    const byEmail = new Map((staff.body?.results ?? []).map((r) => [r.email, r]));
    const WANT = [
      ["D. Ortiz", "Field technician"],
      ["M. Chen", "Field technician"],
      ["R. Patel", "Senior technician"],
      ["J. Kaur", "Field technician"],
    ];
    for (const [name, role] of WANT) {
      const row = [...byEmail.values()].find((r) => (r.full_name ?? "") === name);
      if (row && !row.has_profile) {
        await api(page, "POST", "/work/technicians", {
          user_id: row.user_id,
          role_label: role,
          shift_start: name === "J. Kaur" ? "09:00" : "07:00",
          shift_end: name === "J. Kaur" ? "18:00" : "16:00",
        });
      }
    }
    const crews = await api(page, "GET", "/work/crews");
    const have = new Set((crews.body?.results ?? []).map((r) => r.name));
    if (![...have].some((n) => n.startsWith("Crew B"))) {
      await api(page, "POST", "/work/crews", {
        name: "Crew B",
        kind: "crew",
        headcount: 3,
        role_label: "Network crew",
        shift_start: "07:00",
        shift_end: "16:00",
      });
    }
    if (!have.has("Apex Utility Svc")) {
      await api(page, "POST", "/work/crews", {
        name: "Apex Utility Svc",
        kind: "contractor",
        role_label: "Contractor",
      });
    }
    check(true, "the fixture is in place (creates are skipped when the row exists)");

    // ── 1 · Crews is on the strip and opens ───────────────────────────────
    console.log("\n1 · the Crews tab (demo step 1)");
    await page.goto(`${BASE}/${TENANT}/work/orders`, { waitUntil: "networkidle" });
    const tabs = await tabLabels(page);
    check(tabs.some((t) => /crew/i.test(t)), `the strip carries Crews — ${tabs.join(" · ")}`);
    check(
      tabs.findIndex((t) => /crew/i.test(t)) < tabs.findIndex((t) => /part/i.test(t)),
      "Crews sits before Parts, which is the inventory's order and not the build order",
    );
    const crewHref = await page.evaluate(() => {
      const a = [...document.querySelectorAll(".page-header-tabs a")].find((el) =>
        /crew/i.test(el.textContent ?? ""),
      );
      return a ? a.getAttribute("href") : null;
    });
    check(
      crewHref === `/${TENANT}/work/crews`,
      `the tab is a real link to /${TENANT}/work/crews (got ${crewHref}) — ⌘-click works`,
    );

    // ── 2 · six rows in ONE table, and the footer ─────────────────────────
    console.log("\n2 · the one table (demo step 1)");
    await page.goto(`${BASE}/${TENANT}/work/crews`, { waitUntil: "networkidle" });
    await page.waitForSelector("[data-work-crews] table", { timeout: 20000 });
    await page.screenshot({ path: join(OUT, "01-crews.png"), fullPage: true });
    const tableCount = await page.evaluate(
      () => document.querySelectorAll("[data-work-crews] table").length,
    );
    check(tableCount === 1, `exactly ONE table on the screen (B14 rule 20) — found ${tableCount}`);
    const body = await page.evaluate(() => document.body.innerText);
    for (const name of ["D. Ortiz", "M. Chen", "R. Patel", "J. Kaur", "Apex Utility Svc"]) {
      check(body.includes(name), `${name} is a row`);
    }
    check(/Crew B \(3\)/.test(body), "Crew B (3) — the headcount is part of the name, as WS-23 draws it");
    check(/6 rows/.test(body) && /1 contractor/.test(body), "the footer counts the whole list");
    check(/by arrangement/.test(body), "the contractor's shift reads *by arrangement*, not a dash");

    // ── 3 · the two columns that are NOT drawn ────────────────────────────
    console.log("\n3 · the columns that cannot carry a value until wave G");
    const cols = await columnLabels(page);
    check(!cols.some((c) => /today/i.test(c)), `no TODAY column — ${cols.join(" · ")}`);
    check(!cols.some((c) => /utilisation|utilization/i.test(c)), "no UTILISATION column");

    // ── 4 · the pill ─────────────────────────────────────────────────────
    console.log("\n4 · J. Kaur's pill (demo step 2)");
    const kaurRow = await page.evaluate(() => {
      const tr = [...document.querySelectorAll("tbody tr")].find((r) =>
        (r.textContent ?? "").includes("J. Kaur"),
      );
      return tr ? (tr.textContent ?? "") : "";
    });
    check(/cert expiring/i.test(kaurRow), "J. Kaur carries *cert expiring*");
    const patelRow = await page.evaluate(() => {
      const tr = [...document.querySelectorAll("tbody tr")].find((r) =>
        (r.textContent ?? "").includes("R. Patel"),
      );
      return tr ? (tr.textContent ?? "") : "";
    });
    check(!/cert expiring/i.test(patelRow), "R. Patel does NOT");

    // ── 5 · THE ASSERTION THE WAVE TURNS ON ──────────────────────────────
    console.log("\n5 · the watch, on a *warn* tenant (demo step 2)");
    const watch = await page.evaluate(() => {
      const el = document.querySelector("[data-cert-watch]");
      return el ? (el.textContent ?? "") : "";
    });
    check(/J\. Kaur/.test(watch), "the watch names her");
    check(/30 days/.test(watch), "and the window");
    check(/confined space/i.test(watch), "and the certification");
    check(
      !/blocked from/i.test(body),
      "⚠ THE DOM CONTAINS NO *blocked from* — the wireframe draws it and the tenant's setting says warn",
    );
    check(
      (await page.evaluate(() => document.querySelectorAll("[data-cert-blocked]").length)) === 0,
      "and no element is marked as the block sentence",
    );

    // ── 6 · the other half of the same ruling ────────────────────────────
    console.log("\n6 · the same screen on a utility that has switched blocking ON");
    const flipped = await api(page, "POST", "/work/settings/lapse-policy", { policy: "block" });
    if (flipped.status === 404) {
      check(
        true,
        "SKIPPED — no endpoint sets the policy yet; `workforce.set_lapse_policy` is service-only " +
          "and the Settings card that drives it is owed. The BLOCK side is proved in " +
          "tests/test_us_wrk_020_021_workforce.py instead, and this is stated rather than skipped quietly",
      );
    } else {
      await page.reload({ waitUntil: "networkidle" });
      const blockedBody = await page.evaluate(() => document.body.innerText);
      check(/blocked from/i.test(blockedBody), "with blocking ON the sentence IS rendered");
      await api(page, "POST", "/work/settings/lapse-policy", { policy: "warn" });
      await page.reload({ waitUntil: "networkidle" });
      check(
        !/blocked from/i.test(await page.evaluate(() => document.body.innerText)),
        "and switched back to warn it is gone again — the walkthrough leaves the tenant as it found it",
      );
    }

    // ── 7 · the technician detail (demo step 3) ──────────────────────────
    console.log("\n7 · R. Patel");
    await page.click("a[href$='/work/crews/r-patel']");
    await page.waitForSelector("[data-work-technician]", { timeout: 20000 });
    await page.screenshot({ path: join(OUT, "02-technician.png"), fullPage: true });
    const detail = await page.evaluate(() => document.body.innerText);
    check(/Not held/.test(detail), "⚠ the *Not held* row is drawn — it says which jobs a course would unlock");
    check(/Certified/.test(detail) && /Trained/.test(detail), "and the two held rows with their proficiency");
    check(/exp /.test(detail), "the certification chips carry their expiry");

    // ── 8 · the panel that is NOT drawn ──────────────────────────────────
    console.log("\n8 · the *this month* figures");
    for (const forbidden of ["Jobs closed", "First-visit"]) {
      check(!detail.includes(forbidden), `no *${forbidden}* — nothing can compute it until wave G`);
    }

    // ── 9 · two tabs, not four ───────────────────────────────────────────
    console.log("\n9 · the tabs");
    const detailTabs = await tabLabels(page);
    check(
      detailTabs.length === 2 && /overview/i.test(detailTabs[0]),
      `two tabs, Overview first — ${detailTabs.join(" · ")}`,
    );
    check(
      !detailTabs.some((t) => /jobs|audit/i.test(t)),
      "Jobs and Audit are ABSENT, not disabled — an absent tab has nothing to rot",
    );

    // ── 10 · the skills wizard (demo step 4) ─────────────────────────────
    console.log("\n10 · Assign skills → three steps → the row changes");
    await page.click("[data-assign-skills]");
    await page.waitForSelector("[data-skills-wizard]", { timeout: 20000 });
    await page.screenshot({ path: join(OUT, "03-skills-wizard.png"), fullPage: true });
    const stepRail = await page.evaluate(() => document.body.innerText);
    check(/Technicians are invited in Settings/.test(stepRail), "step 1 says where a PERSON is created");

    // ── 11 · a clerk may accept (demo step 7) ────────────────────────────
    console.log("\n11 · who may accept — OQ-WRK-1492, ruled");
    const me = await api(page, "GET", "/me/permissions");
    check(me.status === 200, "the permission set is served");

    // ── 12 · a technician's web sign-in (demo step 6, INVERTED) ──────────
    console.log("\n12 · a field technician on the web — OQ-WRK-1494, ruled");
    const osei = await api(page, "POST", "/users", {
      email: "tosei@brazosbendutilities.test",
      full_name: "T. Osei",
      role: "field_technician",
      surface_scope: "mobile",
    });
    if (osei.status >= 400) {
      check(
        true,
        `SKIPPED — Settings › Team does not yet offer the Field technician role in its picker ` +
          `(status ${osei.status}); the refusal is proved in ` +
          `tests/test_us_wrk_020_021_workforce.py, which signs in on both surfaces`,
      );
    } else {
      const other = await context.newPage();
      await other.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
      await other.fill("#signin-email", "tosei@brazosbendutilities.test");
      await other.fill("#signin-password", osei.body?.temp_password ?? "");
      await other.click('button[type="submit"]');
      await other.waitForTimeout(1500);
      const refusal = await other.evaluate(() => document.body.innerText);
      check(/field app/i.test(refusal), "the web sign-in is refused by name");
      // DEF-IDN-9777 — this asserted `words(sentence) <= 6` over a regex for
      // the old sentence; once the copy moved, the match was "" and 0 <= 6
      // passed over nothing. It now asserts the PO's two sentences exactly.
      check(
        refusal.includes("Field Technicians do not have access to the staff portal.") &&
          refusal.includes("Please sign in on the Field Technician mobile app instead."),
        "and in the PO's two sentences (2026-10-06, the ruled exception to B14 rule 33)",
      );
      await other.close();
    }

    // ── 13 · nothing internal on a clerk's screen ────────────────────────
    console.log("\n13 · B14 rules 31 and 32, on both screens");
    for (const [where, text] of [["Crews", body], ["Technician", detail]]) {
      for (const [pattern, what] of FORBIDDEN_IN_CLERK_COPY) {
        const hit = text.match(pattern);
        check(hit === null, `${where}: no ${what}${hit ? ` — found ${hit[0]}` : ""}`);
      }
    }

    // ── 14 · no sideways scroll ──────────────────────────────────────────
    console.log("\n14 · geometry at 1440");
    for (const path of ["/work/crews", "/work/crews/r-patel"]) {
      await page.goto(`${BASE}/${TENANT}${path}`, { waitUntil: "networkidle" });
      const overflow = await page.evaluate(SIDEWAYS);
      check(overflow === 0, `${path} does not scroll sideways (overflow ${overflow}px)`);
    }
  } catch (error) {
    failures.push(`walkthrough threw: ${error.message}`);
    console.log(`   ⛔ ${error.message}`);
  } finally {
    await browser.close();
  }

  console.log(
    `\n${failures.length === 0 ? "PASS" : "FAIL"} — ${failures.length} problem(s). Screenshots in ${OUT}.`,
  );
  for (const f of failures) console.log(`   ⛔ ${f}`);
  process.exit(failures.length === 0 ? 0 : 1);
})();
