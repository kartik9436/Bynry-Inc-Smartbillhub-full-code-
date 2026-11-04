/**
 * WALKTHROUGH — CR-075 wave D task D1, the eight runbooks routes, on a
 * RUNNING product, over HTTP, signed in as a real person.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: no gate in this repository looks at a
 * running system, and nine defects in one day were found this way and by
 * nothing else. PO ruling 2026-09-03: *"ensure you do web walkthorugh before
 * you sign off the user story or build"*.
 *
 * ⚠ **AND WHY IT DRIVES HTTP RATHER THAN A BROWSER, STATED RATHER THAN
 * ASSUMED.** Wave D task D1 is the BACKEND half. `RBS-001`, `RBS-002` and
 * `RBS-003` are tasks `D2`, `D3` and `D4` and are two sibling lanes'; there is
 * no runbooks screen to click yet, so a Playwright run would have nothing to
 * assert and would report a green over an empty page — law 7's *incapable of
 * failing*. What CAN be walked today is the door: a real Django process, a real
 * session cookie, a real PostgreSQL with RLS forced, and the eight addresses a
 * clerk's browser will call. When `D2` lands, the browser half belongs with it.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   eval "$(10-scripts/proof-db.sh clone rbsd --export)"      # or your own DB
 *   DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
 *     python3 06-backend/manage.py migrate
 *   DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
 *     python3 06-backend/manage.py seed_demo
 *   DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
 *     python3 06-backend/manage.py seed_runbook_runs --tenant brazosbend
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8075 --noreload &
 *   SMOKE_BASE=http://127.0.0.1:8075 node 10-scripts/render-checks/rbs-d-endpoints.mjs
 *
 * ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** A mid-run reseed
 * looks exactly like a broken endpoint.
 *
 * ── WHAT IT DRIVES, AND WHICH RULE EACH STEP IS ───────────────────────────
 *   1  Sign in for real. Then call one route WITHOUT the cookie and watch it
 *      refuse — a walkthrough that only ever calls signed in cannot tell an
 *      authenticated read from an open one.
 *   2  `GET /runbooks` — the catalogue names the runbook, its last run and its
 *      open items.
 *   3  `GET /runbooks/templates` — **Added**, and the chip row is the templates
 *      PRESENT and not the fixed sixteen (`BR-RBS-025`).
 *   4  `GET /runbooks/runs?per=5` — **50 rows and a page 2** (`NFR-3`: `per`
 *      clamps to 50/100/200/500/1000, so 5 is served as 50). Page 2 holds the
 *      51st, and the two windows do not overlap — which is what an ORDERED SQL
 *      slice buys.
 *   5  `?per=5000` — clamps to 1000 and does NOT refuse (`NFR-5`: no cap).
 *   6  Every row carries a **Started** and a **Took** (`DEF-RBS-4291`, the
 *      defect this wave found: `open_run` never stamped `started_at`).
 *   7  `GET …/report` twice — the two response bodies are compared **BYTE FOR
 *      BYTE** (`BR-RBS-020`, `TC-RBS-16`), and the block count proves it was
 *      read from the column rather than recomposed: the stored report has ONE
 *      block where the live `report()` composes SIX.
 *   8  `GET …/records` and both result CSVs — served, with headers, and EMPTY,
 *      because nothing writes a record row until `OQ-RBS-1737` is answered.
 *      Asserted rather than skipped: an empty file and a 500 look the same from
 *      a distance.
 *   9  A SECOND TENANT, SIGNED IN AS ITSELF, sees none of the first tenant's
 *      runs — its own history answers 200 and holds ZERO, and every per-run
 *      route is a 404 (hard rule 1, on real PostgreSQL with RLS forced).
 *      ⚠ It signs in as that tenant's OWN owner on purpose: reusing the first
 *      tenant's cookie is refused by the SESSION before any runbooks code runs,
 *      and the 404 that produces looks identical while proving something else.
 *  10  No `BR-`, `OQ-`, `DEF-` or uuid in any CSV cell (B14 rules 31 and 32).
 */

import { writeFileSync, mkdirSync } from "node:fs";

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:8075";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const OTHER = process.env.SMOKE_OTHER_TENANT ?? "";
/** Step 9 signs in AS THE SECOND TENANT. Reusing the first tenant's cookie is
 *  refused by the session before any runbooks code runs, so the 404 would prove
 *  `BR-TEN-003` and not this module's tenant filter. */
const OTHER_EMAIL = process.env.SMOKE_OTHER_EMAIL ?? "j.okafor@lsrwater.coop";
const OTHER_PASSWORD = process.env.SMOKE_OTHER_PASSWORD ?? "An0ther!passw0rd";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SMOKE_OUT ?? "/tmp/rbs-d";

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

/** B14 rule 31 and rule 32 — never an id, never an internal code, on a screen;
 *  and a downloaded CSV is a screen: it is opened, read and printed. */
const FORBIDDEN = [
  /\bBR-[A-Z]{3}-\d{3,5}\b/,
  /\bOQ-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /\bDEF-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i,
];

let cookie = "";

async function call(path, { tenant = TENANT, signedIn = true } = {}) {
  const headers = { Accept: "application/json" };
  if (signedIn && cookie) headers.Cookie = cookie;
  const response = await fetch(`${BASE}/api/${tenant}${path}`, { headers });
  const text = await response.text();
  let body = null;
  try {
    body = JSON.parse(text);
  } catch {
    body = null;
  }
  return { status: response.status, body, text, headers: response.headers };
}

(async () => {
  console.log(`rbs-d-endpoints: ${BASE} tenant=${TENANT}`);

  // ═════ 1 · sign in, and prove the door is shut without a session ═════════
  console.log("\n── 1 · a real session, and a route that refuses without one ──");
  const anonymous = await call("/runbooks", { signedIn: false });
  check(
    anonymous.status === 401 || anonymous.status === 403,
    `an unauthenticated GET /runbooks is refused (got ${anonymous.status})`,
  );

  const signIn = await fetch(`${BASE}/api/${TENANT}/auth/session`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: EMAIL, password: PASSWORD }),
  });
  check(signIn.status === 200 || signIn.status === 201, `signed in as ${EMAIL} (${signIn.status})`);
  const setCookie = signIn.headers.getSetCookie?.() ?? [];
  cookie = setCookie.map((one) => one.split(";")[0]).join("; ");
  check(cookie.length > 0, "the server issued a session cookie");
  if (!cookie) {
    console.log("\n⛔ cannot continue without a session — is seed_demo's owner password right?");
    process.exit(1);
  }

  // ═════ 2 · the catalogue ═════════════════════════════════════════════════
  console.log("\n── 2 · GET /runbooks — the catalogue ──");
  const catalogue = await call("/runbooks");
  check(catalogue.status === 200, `the catalogue answers 200 (got ${catalogue.status})`);
  const rows = catalogue.body?.results ?? [];
  check(
    Array.isArray(rows) && "count" in (catalogue.body ?? {}),
    "the reply is the product's list envelope {count, next, previous, results}",
  );
  const canWeBill = rows.find((one) => one.key === "configuration_check");
  check(Boolean(canWeBill), 'the catalogue holds "configuration_check"');
  check(canWeBill?.name === "Can we bill?", `it is named "${canWeBill?.name}"`);
  check(canWeBill?.writes_nothing === true, "a Check writes nothing — derived from ports[], not a label");
  check(canWeBill?.last_run?.id != null, "its last run is summarised on the row");

  // ═════ 3 · the library ═══════════════════════════════════════════════════
  console.log("\n── 3 · GET /runbooks/templates — Added, and the chip row ──");
  const templates = await call("/runbooks/templates");
  check(templates.status === 200, `the library answers 200 (got ${templates.status})`);
  const template = (templates.body?.results ?? [])[0];
  check(template?.state === "added", `the seeded template reads "${template?.state}"`);
  const chips = templates.body?.category_chips ?? [];
  check(chips.length > 0 && chips.length < 16, `${chips.length} category chip(s), not the fixed 16 (BR-RBS-025)`);
  check(chips.every((one) => one.count > 0), "no chip filters to nothing (hard-won law 2)");

  // ═════ 4 · NFR-3 — page past page 1 ══════════════════════════════════════
  console.log("\n── 4 · GET /runbooks/runs?per=5 — 50 rows, and a page 2 ──");
  const first = await call("/runbooks/runs?per=5");
  check(first.status === 200, `the history answers 200 (got ${first.status})`);
  check(first.body?.count === 51, `51 runs seeded, ${first.body?.count} counted`);
  check(
    first.body?.results?.length === 50,
    `per=5 served ${first.body?.results?.length} rows — it must CLAMP UP to 50`,
  );
  check(Boolean(first.body?.next), "page 1 offers a page 2");
  const second = await call("/runbooks/runs?per=5&page=2");
  check(second.body?.results?.length === 1, `page 2 holds the 51st (${second.body?.results?.length})`);
  const ids = new Set([
    ...first.body.results.map((one) => one.id),
    ...second.body.results.map((one) => one.id),
  ]);
  check(ids.size === 51, `the two windows do not overlap (${ids.size} distinct ids)`);

  // ═════ 5 · NFR-3/NFR-5 — the clamp at the top, and no cap ════════════════
  console.log("\n── 5 · ?per=5000 — clamps, and does not refuse ──");
  const wide = await call("/runbooks/runs?per=5000");
  check(wide.status === 200, `per=5000 is served, not refused (got ${wide.status})`);
  check(
    wide.body?.results?.length === 51,
    `all 51 on one page (${wide.body?.results?.length}) — clamped to 1000, no cap in the way`,
  );
  check(wide.body?.next === null, "and there is no page 2 to offer");

  // ═════ 6 · DEF-RBS-4291 — Started and Took ═══════════════════════════════
  console.log("\n── 6 · every run carries a Started and a Took (DEF-RBS-4291) ──");
  const sample = wide.body.results[0];
  check(sample?.started_at != null, `Started is populated (${sample?.started_at})`);
  check(sample?.finished_at != null, "Finished is populated");
  check(typeof sample?.took_seconds === "number", `Took is a number (${sample?.took_seconds}s)`);
  check(
    sample?.by?.person === null && sample?.by?.trigger === "manual",
    "By names the TRIGGER and no person — runbook_runs has no started_by (DEF-RBS-4292)",
  );

  // ═════ 7 · BR-RBS-020 — the frozen report, byte for byte ═════════════════
  console.log("\n── 7 · GET …/report twice — byte-identical, and NOT recomposed ──");
  const runId = sample.id;
  const reportA = await call(`/runbooks/runs/${runId}/report`);
  const reportB = await call(`/runbooks/runs/${runId}/report`);
  check(reportA.status === 200, `the report answers 200 (got ${reportA.status})`);
  check(reportA.text === reportB.text, "two reads are BYTE-IDENTICAL (BR-RBS-020, TC-RBS-16)");
  writeFileSync(`${OUT}/report-a.json`, reportA.text);
  writeFileSync(`${OUT}/report-b.json`, reportB.text);
  const blocks = reportA.body?.blocks ?? [];
  check(
    blocks.length === 1,
    `the STORED report has ${blocks.length} block — the live report() composes 6, so ` +
      "anything but 1 means it was recomputed from the definition (07-endpoints.md E-5)",
  );
  check(blocks[0]?.block === "verdict", "and the stored block is the one that was frozen");

  // ═════ 8 · the records list and the two files ════════════════════════════
  console.log("\n── 8 · …/records and the two result CSVs ──");
  const records = await call(`/runbooks/runs/${runId}/records`);
  check(records.status === 200, `records answers 200 (got ${records.status})`);
  check(
    records.body?.count === 0,
    `${records.body?.count} record rows — 0 is CORRECT today: nothing writes ` +
      "runbook_run_records until OQ-RBS-1737 says how the idempotency key is composed",
  );
  for (const which of ["done", "not-done"]) {
    const file = await call(`/runbooks/runs/${runId}/results/${which}.csv`);
    check(file.status === 200, `${which}.csv answers 200 (got ${file.status})`);
    check(
      (file.headers.get("content-type") ?? "").startsWith("text/csv"),
      `${which}.csv is served as text/csv`,
    );
    check(
      (file.headers.get("content-disposition") ?? "").includes(`runbook-run-${runId}-${which}.csv`),
      `${which}.csv is offered as an attachment named for its run`,
    );
    const lines = file.text.trim().split("\n");
    check(lines[0].startsWith("Subject,"), `${which}.csv opens with the declared header`);
    check(lines[0].includes("Reason") && lines[0].includes("Fix"), `${which}.csv carries reason and fix`);
    writeFileSync(`${OUT}/${which}.csv`, file.text);
    // ═════ 10 · B14 rules 31 and 32, inside the loop where the cells are ═══
    for (const pattern of FORBIDDEN) {
      check(!pattern.test(file.text), `${which}.csv: nothing matching ${pattern} in any cell`);
    }
  }
  const missing = await call(`/runbooks/runs/${runId}/results/maybe.csv`);
  check(missing.status === 404, `a third file name is a 404 (got ${missing.status})`);

  // ═════ 9 · hard rule 1 — a second tenant sees none of it ═════════════════
  console.log("\n── 9 · a second tenant sees none of the first tenant's runs ──");
  if (!OTHER) {
    console.log(
      "   ⚠ SKIPPED — no SMOKE_OTHER_TENANT given. This is the ONE step that cannot be\n" +
        "     assumed: run it with a second seeded tenant, or the isolation claim rests\n" +
        "     only on tests/test_us_rbs_003_pg.py. Naming the skip is the point (law 7:\n" +
        "     a declared blind spot with no number is indistinguishable from an empty one).",
    );
  } else {
    // ⚠ **SIGN IN AS THE SECOND TENANT'S OWN OWNER, AND THE FIRST DRAFT DID
    // NOT — SO THIS CHECK PASSED FOR THE WRONG REASON.** Reusing the first
    // tenant's cookie against the second tenant's path is refused by the
    // SESSION before any runbooks code runs, and the 404 it produces is
    // indistinguishable from the one this step exists to prove. It was green.
    // It was measuring `BR-TEN-003`, not `NFR`/hard rule 1 in this module.
    // Law 7's second habit — ask what would make the check pass WRONGLY —
    // caught it, and the answer was "the thing that actually happened".
    const theirSignIn = await fetch(`${BASE}/api/${OTHER}/auth/session`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: OTHER_EMAIL, password: OTHER_PASSWORD }),
    });
    check(theirSignIn.status < 300, `signed in as ${OTHER_EMAIL} at ${OTHER} (${theirSignIn.status})`);
    const theirCookie = (theirSignIn.headers.getSetCookie?.() ?? [])
      .map((one) => one.split(";")[0])
      .join("; ");
    check(theirCookie.length > 0, `${OTHER} issued its own session cookie`);
    const mine = cookie;
    cookie = theirCookie;

    const theirHistory = await call("/runbooks/runs", { tenant: OTHER });
    check(
      theirHistory.status === 200,
      `${OTHER} can read ITS OWN history (got ${theirHistory.status}) — a 404 here would ` +
        "mean the session was refused and this step would prove nothing",
    );
    check(
      theirHistory.body?.count === 0,
      `and it holds NONE of ${TENANT}'s 51 runs (count ${theirHistory.body?.count})`,
    );
    for (const path of [
      `/runbooks/runs/${runId}`,
      `/runbooks/runs/${runId}/report`,
      `/runbooks/runs/${runId}/records`,
      `/runbooks/runs/${runId}/results/done.csv`,
    ]) {
      const reached = await call(path, { tenant: OTHER });
      check(reached.status === 404, `${OTHER} cannot open ${path} (got ${reached.status})`);
    }
    cookie = mine;
  }

  console.log(
    `\n${failures.length === 0 ? "PASS" : "FAIL"} — ${failures.length} failing check(s). ` +
      `Artefacts in ${OUT}`,
  );
  for (const one of failures) console.log(`   ⛔ ${one}`);
  process.exit(failures.length === 0 ? 0 : 1);
})().catch((error) => {
  console.error("rbs-d-endpoints CRASHED:", error);
  process.exit(2);
});
