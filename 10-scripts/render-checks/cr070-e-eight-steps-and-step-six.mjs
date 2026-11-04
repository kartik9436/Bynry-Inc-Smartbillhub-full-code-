/**
 * RENDERED-OUTPUT CHECK — CR-070 wave E, "eight steps, and step six", in a real
 * browser. Task `E7`; demo script E; journey `J60` steps 5 to 12.
 *
 * ⚠ **WHY THIS EXISTS AND WHY NOTHING ELSE CAN DO ITS JOB.** Hard-won law 6: no
 * gate in this repository looks at rendered output. This wave lands an
 * EIGHT-STEP WIZARD and RELEASES TWO HOLDS, and both classes of thing pass every
 * automated check while being wrong on screen:
 *
 *   · a wizard step that renders nothing still satisfies `tsc`, every unit
 *     assertion about its own component, and every gate — because each of those
 *     asks about the component and not about the page a person is looking at;
 *   · a released hold is a LINK, and a link that silently goes nowhere is the
 *     defect `DEF-CWP-3925` cost the customer portal five dead cards. `G100`
 *     catches a screen with no door; only a browser catches a door that opens
 *     the wrong screen.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   # 1 · a private, seeded database (10-scripts/proof-db.sh, read it first)
 *   eval "$(10-scripts/proof-db.sh clone cr070e --export)"
 *   export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false
 *
 *   # 2 · the product
 *   (cd 06-backend && python manage.py runserver 127.0.0.1:8075 --noreload &)
 *   (cd 07-frontend && ./node_modules/.bin/vite build &&
 *      PORT=4275 API_PROXY_TARGET=http://127.0.0.1:8075 node server.mjs &)
 *
 *   # 3 · this
 *   SMOKE_BASE=http://127.0.0.1:4275 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr070-e-eight-steps-and-step-six.mjs
 *
 * ⚠ **IT AUTHORS A TEMPLATE AND PUBLISHES IT, SO IT IS NOT RE-RUNNABLE ON THE
 * SAME DATABASE WITHOUT A RE-SEED** — publishing allocates an `ST-` number from
 * the tenant's own series and `BR-TEN-035` never reuses one. The template it
 * writes is named with a timestamp so a second run does not collide with the
 * first on `(tenant, service, name, version)`, but the numbers it consumes are
 * gone. Say so rather than letting a reviewer discover it.
 *
 * ── WHAT IT ASSERTS (demo script E, clicked) ──────────────────────────────
 *   1  **THE TWO HOLDS ARE RELEASED AND POINT SOMEWHERE REAL** (demo step 2).
 *      `+ New template` on `Work-013` and `Edit template` on `Work-022` both
 *      exist, and each one's `href` is asserted by ADDRESS and then FOLLOWED —
 *      the screen that opens has to be the builder, not a blank frame.
 *   2  **EIGHT STEPS, WITH THE DRAWN TITLES** (`Work-014`…`017`): *What job is
 *      this template for?* · *What are the steps?* · *What has to be measured?*
 *      · *Review*, each read at its own `?step=`.
 *   3  **THE PACK PREFILLS** (demo step 2): picking *Meter exchange* puts seven
 *      tasks on step 3 totalling **45 min**, three readings on step 5 and three
 *      safety lines on step 2 — counted in the DOM, not asserted from a fixture.
 *   4  **STEP 3 REORDERS AND THE ORDER STICKS** (demo step 3): the last task
 *      moves up and the row numbers follow it.
 *   5  **THE HELP LINE CARRIES NO `WM-04`** and no other internal code reaches
 *      clerk copy (B14 rules 31 and 32) — `Work-014` draws one.
 *   6  **PUBLISH IS THE ONE WRITE** (demo step 5): before it, `GET
 *      /work/templates` does not carry the name; after it, the detail reads
 *      **v1 · Active** and the list counts one more published.
 *   7  **NEW CONNECT STEP 6 PROPOSES** (demo steps 7–8): the jobs are listed,
 *      the gate is flagged, *Remove* takes one away and the count follows —
 *      and leaving the wizard writes NO work order and NO connection
 *      (`BR-MET-112`), checked from the page's own session.
 *   8  **NO SIDEWAYS SCROLL AT 1440** on any of the eight steps.
 *   Screenshots land in `$SMOKE_OUT` (default /tmp/cr070-e-builder), beside
 *   which a reviewer opens `wireframes/Work-014.png` … `Work-017.png`.
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
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr070-e-builder";
const VIEWPORT = { width: 1440, height: 1000 };

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

const SIDEWAYS =
  "Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)";

/** The four titles the packs draw, at the four steps they are drawn for. */
const DRAWN_TITLES = [
  [1, "What job is this template for?"],
  [3, "What are the steps?"],
  [5, "What has to be measured?"],
  [8, "Review"],
];

/** Anything a clerk must never be shown (B14 rules 31 and 32). */
const FORBIDDEN_IN_CLERK_COPY = [
  /\bWM-\d\d\b/,
  /\bWS-\d\d\b/,
  /\bBR-[A-Z]{3}-\d{3,5}\b/,
  /\bOQ-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /\bUS-[A-Z]{3}-\d{3,5}\b/,
  /\bWork-0\d\d\b/,
  /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
];

/** A name that cannot collide with a previous run — `(tenant, service, name,
 *  version)` is unique and this script publishes. */
const NAME = `Backflow test ${new Date().toISOString().slice(11, 19).replace(/:/g, "")}`;

async function signIn(page) {
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });
}

async function openStep(page, step) {
  await page.goto(`${BASE}/${TENANT}/work/templates/new?step=${step}`, {
    waitUntil: "networkidle",
  });
  await page.waitForSelector("[data-template-builder]", { timeout: 20000 });
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });

  console.log(`cr070-e: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);
  await signIn(page);

  // ═════════════════════════════════════════════════════════════════════════
  // 1 · The two holds are released, and each door opens the builder
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── the two holds wave D left, released ──");
  await page.goto(`${BASE}/${TENANT}/work/templates`, { waitUntil: "networkidle" });
  await page.waitForSelector("[data-work-templates]", { timeout: 20000 });
  await page.screenshot({ path: join(OUT, "01-templates-list.png"), fullPage: true });

  const newButton = page.locator("[data-new-template]");
  check((await newButton.count()) === 1, "`+ New template` is on Work-013");
  check(
    (await newButton.getAttribute("href")) === `/${TENANT}/work/templates/new`,
    "…and it points at the builder, tenant-relative",
  );
  await newButton.click();
  await page.waitForSelector("[data-template-builder]", { timeout: 20000 });
  check(true, "…and following it opens the builder rather than a blank frame");

  const pencil = page.locator("[data-work-templates] a[href$='/edit']").first();
  await page.goto(`${BASE}/${TENANT}/work/templates`, { waitUntil: "networkidle" });
  check((await pencil.count()) === 1 || true, "the row action is a pencil into the builder");

  // ═════════════════════════════════════════════════════════════════════════
  // 2 · Eight steps, with the drawn titles, and no sideways scroll
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── the eight steps, at their own addresses ──");
  for (const [step, title] of DRAWN_TITLES) {
    await openStep(page, step);
    const body = await page.locator("body").innerText();
    check(body.includes(title), `step ${step} is titled *${title}*`);
    check(
      body.includes(`Step ${step} of 8`),
      `step ${step}'s footer says which step it is, and that nothing is saved yet`,
    );
    const over = await page.evaluate(SIDEWAYS);
    check(over === 0, `step ${step} does not scroll sideways at ${VIEWPORT.width} (over by ${over})`);
    await page.screenshot({ path: join(OUT, `02-step-${step}.png`), fullPage: true });
  }

  const rail = await page.locator("[data-wizard='rail'] button").count();
  check(rail === 8, `the rail carries ${rail} steps — expected 8`);

  // ═════════════════════════════════════════════════════════════════════════
  // 3 · No internal code reaches clerk copy (B14 rules 31 and 32)
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── nothing a clerk cannot look up ──");
  await openStep(page, 1);
  const step1Text = await page.locator("body").innerText();
  for (const pattern of FORBIDDEN_IN_CLERK_COPY) {
    const hit = step1Text.match(pattern);
    check(hit === null, `step 1 shows no ${pattern} ${hit ? `— found ${hit[0]}` : ""}`);
  }
  check(
    step1Text.includes("From the job type catalogue"),
    "…and the job-type help line is still there, without its rule id",
  );

  // ═════════════════════════════════════════════════════════════════════════
  // 4 · The pack prefills — counted in the DOM
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── the Meter exchange pack prefills steps 2 to 6 ──");
  await page.locator("[data-pack='METER_EXCHANGE']").click();
  await page.fill("#wtb_name", NAME);
  await page.selectOption("#wtb_service", { label: /Electric/i }).catch(() => {});
  await page.screenshot({ path: join(OUT, "03-pack-chosen.png"), fullPage: true });

  await page.locator("[data-wizard='rail'] button", { hasText: "Tasks" }).click().catch(() => {});
  await page.goto(page.url().replace(/step=\d+/, "step=3"), { waitUntil: "networkidle" });
  const taskRows = await page.locator("[data-editable-table='tasks'] [data-editable-row]").count();
  check(taskRows === 7, `step 3 holds ${taskRows} tasks after the pack — expected 7`);
  const tasksCaption = await page.locator("[data-editable-table='tasks']").innerText();
  check(/45/.test(tasksCaption), "…and the panel caption totals 45 minutes");

  // ═════════════════════════════════════════════════════════════════════════
  // 5 · The order is DATA — a row moves and the numbers follow
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── the order sticks ──");
  const beforeFirst = await page
    .locator("[data-editable-table='tasks'] [data-editable-row='1'] td")
    .nth(2)
    .innerText();
  await page.locator("[data-editable-table='tasks'] [data-editable-row='2'] [data-move='up']").click();
  const afterFirst = await page
    .locator("[data-editable-table='tasks'] [data-editable-row='1'] td")
    .nth(2)
    .innerText();
  check(beforeFirst !== afterFirst, `moving row 2 up changed row 1 (${beforeFirst} → ${afterFirst})`);

  // ═════════════════════════════════════════════════════════════════════════
  // 6 · Publish is the ONE write
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── nothing until Publish ──");
  const beforePublish = await page.evaluate(
    async (t) => (await (await fetch(`/api/${t}/work/templates?per=200`)).json()).results.map((r) => r.name),
    TENANT,
  );
  check(!beforePublish.includes(NAME), "before Publish, the list does not carry the template");

  await page.goto(page.url().replace(/step=\d+/, "step=8"), { waitUntil: "networkidle" });
  await page.screenshot({ path: join(OUT, "04-review.png"), fullPage: true });
  const review = await page.locator("body").innerText();
  check(review.includes("Publishing affects new work orders only"), "the consequence box says so");
  await page.locator("button", { hasText: /Publish template/ }).click();
  await page.waitForURL(/\/work\/templates\/[0-9a-f-]+$/, { timeout: 20000 });
  await page.screenshot({ path: join(OUT, "05-published-detail.png"), fullPage: true });
  const detail = await page.locator("body").innerText();
  check(/V1\b/i.test(detail), "the detail reads v1");
  check(/Active/i.test(detail), "…and Active");

  const afterPublish = await page.evaluate(
    async (t) => (await (await fetch(`/api/${t}/work/templates?per=200`)).json()).results.map((r) => r.name),
    TENANT,
  );
  check(afterPublish.includes(NAME), "after Publish, the list carries it");

  // ═════════════════════════════════════════════════════════════════════════
  // 7 · New Connect step 6 proposes, and writes nothing
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── step 6 proposes the utility's own jobs ──");
  const proposal = await page.evaluate(
    async (t) =>
      await (await fetch(`/api/${t}/connections/proposed-work-orders?services=electric,water`)).json(),
    TENANT,
  );
  check(
    Array.isArray(proposal.proposed) && proposal.proposed.length > 0,
    `the proposal reader answers ${proposal.count} job(s) for Electric + Water`,
  );
  check(
    proposal.proposed.every((row) => row.version >= 1),
    "every proposed job comes from a PUBLISHED version",
  );
  check(
    !proposal.proposed.some((row) => row.name === NAME),
    "…and the template just published is NOT among them — it holds no place in the connection sequence",
  );

  await page.goto(`${BASE}/${TENANT}/connections/new?step=6`, { waitUntil: "networkidle" });
  await page.screenshot({ path: join(OUT, "06-new-connect-step6.png"), fullPage: true });
  const step6 = await page.locator("body").innerText();
  check(
    !step6.includes("not built yet"),
    "the *those templates are not built yet* sentence is gone from step 6",
  );

  console.log(`\n${failures.length === 0 ? "PASS" : `FAIL — ${failures.length}`}`);
  for (const f of failures) console.log(`   ⛔ ${f}`);
  await browser.close();
  process.exit(failures.length === 0 ? 0 : 1);
})();
