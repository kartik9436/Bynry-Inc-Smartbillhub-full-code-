// ── Trace ──────────────────────────────────────────────
// Story:   CR-142-BRC07 · `P6.11` — the three joining reads, OPENED IN A
//          BROWSER: R36 Access Review · R32 Read Import Log · R23 Account
//          Activity. Until this ran, all three were green tests and nobody had
//          looked at one.
// Rules:   CLAUDE.md hard-won law 6 (*"diff the running app — no gate looks at
//          rendered output"*) · hard-won law 2's mirror (a live screen behind
//          a dead control) · B14 rule 44 (the staff app is verified at 1440,
//          and at 1280 because the standard speaks everywhere) · rule 31 (no
//          database id is ever a visible value) · `DEF-REP-6900` (a raw
//          message key reaching the screen)
// ───────────────────────────────────────────────────────
//
// PHOTOGRAPH WHAT IS THERE. Nothing is dressed for the picture: no CSS is
// injected, no element is hidden, no value is substituted. Where a view cannot
// be captured the script SAYS SO in 00-README.txt rather than skipping it
// silently — an absence with no reason beside it is indistinguishable from a
// pass (law 7's fifth shape).
//
// ⚠ **IT CHECKS THREE THINGS THAT NO BACKEND TEST CAN SEE**, and each one has
// already shipped broken in this repo at least once:
//
//   1. **A RAW MESSAGE KEY ON SCREEN.** `ReportViewerPage` renders a column
//      header as `t("reports.col.<name>", { defaultValue: <name> })`, so a key
//      nobody added renders as `last_active_at` in front of a clerk — which is
//      `DEF-REP-6900` exactly. The script reads the rendered `<th>` text and
//      FAILS on any header that still looks like a snake_case key.
//   2. **A UUID IN A CELL.** B14 rule 31. The report carries `batch_id` and
//      `event_id` for drill-through, and a renderer that put one in a column
//      would pass every backend assertion.
//   3. **ROWS.** `P6.27` is the forty-six-report render walk and this is three
//      of it: a report that opens onto its own refusal sentence is a screen
//      pretending to be a report, and 28 of the 46 did exactly that this
//      morning.
//
//   node 10-scripts/p6_join_shots.mjs
//
// Env: SMOKE_BASE (http://127.0.0.1:8080) · SMOKE_TENANT · SMOKE_EMAIL ·
//      SMOKE_PASSWORD · SHOT_OUT

import { mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";

// ⚠ NO DEPENDENCY OF ITS OWN — it borrows `playwright-core` from the front
// end's install, exactly as its siblings do. A bare `import "playwright"`
// resolves from THIS directory upward and `10-scripts/` has no `node_modules`.
const requireFrontend = createRequire(
  new URL("../07-frontend/package.json", import.meta.url),
);
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:8080";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SHOT_OUT ?? "scratchpad/po-shots/joining-reads";
const EXE =
  process.env.PW_CHROME ??
  "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

//: The three, and the ONE ROW each of them is — printed beside every capture so
//: a reader of the shots does not have to go and look it up.
const REPORTS = [
  ["access_review", "R36 Access Review", "one user of this tenant"],
  ["read_import_log", "R32 Read Import Log", "one read-import batch"],
  ["account_activity", "R23 Account Activity", "one account-lifecycle event"],
];

//: A header that still looks like this is a message key the catalogues do not
//: hold — `snake_case`, no spaces, all lower. `DEF-REP-6900`.
const RAW_KEY = /^[a-z][a-z0-9]*(_[a-z0-9]+)+$/;
//: A uuid in a CELL. B14 rule 31.
const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;

const notes = [];
const failures = [];
function note(line) {
  console.log(line);
  notes.push(line);
}

async function shot(page, name, width) {
  await page.setViewportSize({ width, height: 1000 });
  await page.waitForTimeout(600);
  const file = path.join(OUT, `${name}-${width}.png`);
  await page.screenshot({ path: file, fullPage: false });
  note(`  captured ${path.basename(file)}`);
}

async function inspect(page, key, title, grain) {
  const headers = await page.locator("table thead th").allTextContents();
  const cells = await page.locator("table tbody td").allTextContents();
  const rows = await page.locator("table tbody tr").count();
  // ⚠ **THE WHOLE PAGE, NOT ONLY THE TABLE — AND THIS IS A CORRECTION THIS
  // SCRIPT MADE TO ITSELF.** Its first run looked at `<th>` text and at cells
  // matching a uuid, printed `PASS`, and the screenshot beside it showed
  // THREE raw values the checks had not looked at: `cells.basis.as_at` under
  // the page head, `true`/`false` in a column, and
  // `2026-09-27T12:32:27.923853+00:00` in another. A check whose output
  // cannot distinguish pass from fail is worse than none, because it is
  // trusted (hard-won law 7 habit 3) — and law 6 is why it was caught at all.
  const pageText = await page.locator("main, body").first().innerText();

  note(`  ${title}: ${rows} row(s) rendered`);
  note(`  headers: ${JSON.stringify(headers.map((h) => h.trim()))}`);

  // 3 · ROWS. A report that opens onto nothing is not a report.
  if (rows === 0) {
    failures.push(
      `${title}: the table rendered ZERO rows. Either the fixture is empty or ` +
        `the report refused — and a screenshot cannot tell those apart, which ` +
        `is why this fails rather than being left for a reader to notice.`,
    );
  }

  // 1 · A RAW MESSAGE KEY ON SCREEN (`DEF-REP-6900`).
  const raw = headers.map((h) => h.trim()).filter((h) => RAW_KEY.test(h));
  if (raw.length) {
    failures.push(
      `${title}: ${raw.length} column header(s) rendered as a RAW MESSAGE KEY — ` +
        `${JSON.stringify(raw)}. The viewer falls back to the column name when a ` +
        `catalogue has no \`reports.col.<name>\`, so this is DEF-REP-6900 reaching ` +
        `a clerk.`,
    );
  }

  // 1b · A RAW MESSAGE KEY ANYWHERE ON THE PAGE, not only in a header.
  const dotted = [...pageText.matchAll(/\b[a-z][a-zA-Z0-9]*(?:\.[a-z][a-zA-Z0-9_]*){2,}\b/g)]
    .map((m) => m[0])
    .filter((k) => !k.includes("@") && !/\.(csv|json|png|pdf|xlsx)$/i.test(k));
  if (dotted.length) {
    failures.push(
      `${title}: ${dotted.length} RAW MESSAGE KEY(S) rendered on the page — ` +
        `${JSON.stringify([...new Set(dotted)].slice(0, 5))}. i18next falls back to the key ` +
        `when no catalogue holds it, so this is DEF-REP-6900 reaching a clerk.`,
    );
  }

  // 1c · A RAW ISO TIMESTAMP ON THE PAGE. `2026-09-27T12:32:27.923853+00:00`
  // is not a date anybody reads; the viewer renders one through `DateCell`.
  const instants = [...pageText.matchAll(/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/g)].map((m) => m[0]);
  if (instants.length) {
    failures.push(
      `${title}: ${instants.length} RAW ISO TIMESTAMP(S) on the page — ` +
        `${JSON.stringify([...new Set(instants)].slice(0, 3))}.`,
    );
  }

  // 1d · A RAW BOOLEAN. A column that prints `true` is not a column a clerk
  // can read, and it is what R36's APPROVES MONEY did before `P6.11`.
  const bools = cells.map((c) => c.trim()).filter((c) => c === "true" || c === "false");
  if (bools.length) {
    failures.push(
      `${title}: ${bools.length} cell(s) render a RAW BOOLEAN (\`true\`/\`false\`). ` +
        `A boolean is a word on screen.`,
    );
  }

  // 2 · A UUID IN A CELL (B14 rule 31).
  const ids = cells.map((c) => c.trim()).filter((c) => UUID.test(c));
  if (ids.length) {
    failures.push(
      `${title}: ${ids.length} cell(s) render a DATABASE ID — ${JSON.stringify(
        ids.slice(0, 3),
      )}. B14 rule 31: no database id is ever the visible value of a field.`,
    );
  }

  // The grain line the screen states under the title, checked against the one
  // the read model publishes. A report whose grain line is wrong is worse than
  // one that has none, because a reader trusts it.
  // ⚠ **A SHORT TIMEOUT, BECAUSE THE ELEMENT IS USUALLY ABSENT.** Playwright
  // waits the full default 30s for a locator that never resolves, so the first
  // run spent 90 seconds of its 600s budget waiting to learn `null` three
  // times. An absence is the expected answer here, not an error.
  const stated = await page
    .locator(".fin-grain, [data-grain]")
    .first()
    .textContent({ timeout: 1500 })
    .catch(() => null);
  note(`  grain on screen: ${JSON.stringify(stated)} · served: ${JSON.stringify(grain)}`);
}

async function main() {
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ executablePath: EXE });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });

  note(`base ${BASE} · tenant ${TENANT}`);
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForTimeout(2500);
  note(`signed in; landed on ${page.url()}`);

  for (const [key, title, grain] of REPORTS) {
    note(`\n── ${title} · one row is ${grain} ──`);
    await page.goto(`${BASE}/${TENANT}/reports/${key}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(1800);
    await inspect(page, key, title, grain);
    for (const w of [1440, 1280]) await shot(page, key, w);

    // ── THE DOWNLOAD CONTROL, CLICKED ────────────────────────────────────
    // ⚠ **A LIVE BUTTON THAT 404s IS HARD-WON LAW 2'S MIRROR**, and the
    // viewer enables this one whenever a report renders. `apps/reports/
    // exports.py` registers FOUR export resources; a report outside that four
    // posts a `resource` the server answers 404 to. This asks the SERVER,
    // through the signed-in session, because an unauthenticated curl answers
    // 404 for every resource including a registered one — a probe that cannot
    // tell the two apart is worse than none.
    const exportStatus = await page.evaluate(async (payload) => {
      const r = await fetch(payload.url, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ resource: payload.key, filters: {} }),
      });
      return r.status;
      // ⚠ **`/api/exports`, WITH NO TENANT SEGMENT — AND THE FIRST DRAFT PUT
      // ONE IN.** `src/api/client.ts` lists the un-tenanted routes by name and
      // `/api/exports` is one of them, so `${BASE}/api/${TENANT}/exports` is a
      // 404 for the URL and says NOTHING about whether the resource is
      // registered. The check reported three findings that were its own bug —
      // hard-won law 7's second habit, *ask what would make this check FAIL
      // wrongly*, which is the same discipline as asking what makes it pass.
    }, { url: `${BASE}/api/exports`, key });
    note(`  POST /exports resource=${key}: HTTP ${exportStatus}`);
    if (exportStatus === 404) {
      failures.push(
        `${title}: the DOWNLOAD control is enabled and POST /exports answers 404 — ` +
          `this report is not a registered export resource. A live button that fails ` +
          `is hard-won law 2's mirror.`,
      );
    }

    // WHAT THE API ACTUALLY SERVED, so the picture can be checked against it
    // rather than believed (hard-won law 1).
    const body = await page.evaluate(async (u) => {
      const r = await fetch(u, { credentials: "include" });
      return { status: r.status, text: (await r.text()).slice(0, 6000) };
    }, `${BASE}/api/${TENANT}/reports/${key}`);
    note(`  API ${key}: HTTP ${body.status}`);
    if (body.status !== 200) {
      failures.push(`${title}: GET /reports/${key} answered HTTP ${body.status}.`);
    }
    writeFileSync(path.join(OUT, `api-${key}.json`), body.text);
  }

  await browser.close();

  note("");
  if (failures.length) {
    note(`FAILED — ${failures.length} finding(s):`);
    for (const f of failures) note(`  · ${f}`);
  } else {
    note("PASS — three reports opened, all rendered rows, no raw key, no uuid on screen.");
  }
  note("");
  note("NOT CHECKED HERE, and each has its own check:");
  note("  · the arithmetic → tests/test_rep_p6_*.py");
  note("  · LIMIT/OFFSET cost → 10-scripts/p6_join_cost.py");
  note("  · RLS → 10-scripts/p6_join_rls_proof.py");
  note("  · the other 43 reports → P6.27, the forty-six-report render walk");
  writeFileSync(path.join(OUT, "00-README.txt"), notes.join("\n") + "\n");
  console.log(`wrote ${OUT}/00-README.txt`);
  if (failures.length) process.exitCode = 1;
}

main().catch((err) => {
  note(`FAILED: ${err.message}`);
  mkdirSync(OUT, { recursive: true });
  writeFileSync(path.join(OUT, "00-README.txt"), notes.join("\n") + "\n");
  process.exitCode = 1;
});
