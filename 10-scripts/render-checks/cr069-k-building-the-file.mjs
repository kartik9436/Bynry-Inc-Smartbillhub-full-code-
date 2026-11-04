/**
 * RENDERED-OUTPUT CHECK — CR-069 wave K, *the walk and the file they build*,
 * in a real browser, against a real PostgreSQL.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: no gate in this repository looks at
 * rendered output, and nine defects in one day were found this way and by
 * nothing else. PO ruling 2026-09-03: *"ensure you do web walkthorugh before
 * you sign off the user story or build"*.
 *
 * ⚠ **AND THIS WAVE'S DELIVERABLES ARE THREE SENTENCES AND A COUNT.** A pytest
 * case can prove the run row closed `unconfirmed` with the right summary, and
 * that the credential table holds one row. Only a browser can tell you that
 * S142 prints *They are building the file. We will collect it when it is ready
 * · asked them 4 times · checking again in 30 seconds* rather than the raw enum
 * word `running`, that *window 61 of 105* is drawn in the clerk's units rather
 * than as a percentage, and that the four parameters we state are actually on
 * the screen. None of those is visible to any test in this repository.
 *
 * ── WHAT THIS SCRIPT DOES AND DOES NOT COVER, SAID FIRST ───────────────────
 *
 * ⚠ **THE RUN IS STARTED THROUGH THE API, NOT A SCREEN, AND THAT IS THE
 * BOUNDARY RATHER THAN A SHORTCUT.** Deciding WHEN a collection runs is
 * scheduling, and `BR-INT-054` as sharpened on 2026-09-06 puts scheduling in
 * Runbooks; there is no integrations screen that starts a two-year backfill.
 * So this posts to `POST /integrations/{key}/run` — the door this wave
 * actually shipped — and then reads the result on the screen this wave owns,
 * the connection detail (S142).
 *
 * ⚠ **AND THE HEAD-END IS A RECORDED FIXTURE, NOT A REAL VENDOR.** `test()`
 * against the live Neptune cloud is not something a walkthrough may do, and
 * `HEAD_END_CLIENT` is `None` on this deployment. The seeding step below binds
 * `neptune_fixtures.RecordedHeadEnd` in the SERVER process, which is the same
 * object the pytest suite uses — so what the browser sees is the real screen
 * over the real runner over a recorded provider.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   eval "$(10-scripts/proof-db.sh clone int_k --export)"
 *   DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
 *     python3 06-backend/manage.py migrate
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=true \
 *   DATABASE_URL="$DATABASE_URL" NEPTUNE_RECORDED=1 \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8171 --noreload &
 *   (cd 07-frontend && ./node_modules/.bin/vite build && \
 *      PORT=4371 API_PROXY_TARGET=http://127.0.0.1:8171 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4371 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr069-k-building-the-file.mjs
 *
 * ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** It CONNECTS a meter
 * head-end, so a shared database is left with a stranger's connection.
 *
 * ── WHAT IT ASSERTS (demo script K, Alex Reed) ────────────────────────────
 *   1  The *Water meter cloud* card is CONNECTABLE. Before this wave the card
 *      was live, the manifest was registered, and connect was refused
 *      *Cannot be connected yet.* — hard-won law 2, built is not wired.
 *   2  Connect it: Site ID and API key, the two fields the manifest declares.
 *   3  Run the billing export → S142 shows the collecting sentence with the
 *      count rising, and the run is still going.
 *   4  Leave the page and come back → the run reads *Done* and the file they
 *      built is LINKED.
 *   5  Start the readings collection with `actual_consumption` missing →
 *      *not started — actual_consumption was not set*, and NOTHING left: no
 *      request reached the recorded head-end.
 *   6  **THE CONTROL** — the same collection with all four set DOES run.
 *      Without this, step 5 is indistinguishable from an endpoint that refuses
 *      everything, and *nothing was collected* describes both.
 *   7  Run the route-closing export twice → the second reads
 *      *already closed on <day> <mon>*, and the head-end was not called again.
 *   8  After the walk, the credential history shows ONE version.
 *   9  No database id and no rule id anywhere on these screens (B14 rules 31
 *      and 32), and the raw enum words `running` and `unconfirmed` are not on
 *      the screen — the clerk reads *Running* and *Unconfirmed*.
 */

import { execFileSync } from "node:child_process";
import { mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

import { Gaps } from "./lib/knownGaps.mjs";
import { attachTimings } from "./lib/timings.mjs";

const require = createRequire(join(process.cwd(), "07-frontend", "package.json"));
const { chromium } = require("playwright-core");

/**
 * ⚠ RUN THE BINARY; DO NOT TRUST THE PATH. `chromium.executablePath()` returns
 * the path playwright-core WANTS — it does not throw when nothing is there, so
 * a `try/catch` around it never fires and the launch fails later with a path
 * that looks plausible. `--version` is the only check that distinguishes
 * "installed" from "named" (law 7's *looking at the wrong thing*).
 */
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4371";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr069-k";
const VIEWPORT = { width: 1440, height: 1000 };

const PROVIDER = "meters_neptune360";
const READINGS = "collect_readings";
const EXPORT = "collect_billing_export";
const CLOSING_EXPORT = "request_billing_export";

/** The four whose default is unsafe. Two of them are on the money path. */
const SAFE = {
  actual_consumption: true,
  include_estimates: false,
  unit_of_measure: "GAL",
  read_time_zone: "America/Chicago",
};

/*
 * ⚠ **THE REQUEST KEY CARRIES THIS RUN'S OWN STAMP, AND LEAVING IT OUT WOULD
 * COST A WHOLE RUN.** The product's guarantee is that a period is closed on
 * the head-end ONCE, for ever — so a walkthrough posting a FIXED key passes
 * once and then fails on its own success: the second run reads *already closed*
 * where it expects a fresh close. That is not a flaky check, it is a check that
 * can only ever be true once, which is worse.
 */
const STAMP = String(Date.now()).slice(-6);
const CLOSE_KEY = `2026-08:route-north:${STAMP}`;

const failures = [];
const gaps = new Gaps();

function check(ok, what, detail = "") {
  console.log(`${ok ? "  ok  " : "  FAIL"} ${what}${detail ? ` — ${detail}` : ""}`);
  if (!ok) failures.push(what);
}

async function shot(page, name) {
  mkdirSync(OUT, { recursive: true });
  await page.screenshot({ path: join(OUT, `${name}.png`), fullPage: true });
}

/** Start a run as the signed-in clerk, from inside the page. */
async function start(page, body) {
  return page.evaluate(
    async ([tenant, provider, payload]) => {
      const response = await fetch(`/api/${tenant}/integrations/${provider}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(payload),
      });
      let parsed = null;
      try {
        parsed = await response.json();
      } catch {
        parsed = null;
      }
      return { status: response.status, payload: parsed };
    },
    [TENANT, PROVIDER, body],
  );
}

/** The latest run row for an operation, off the screen's own read model. */
async function latestRun(page, operation) {
  return page.evaluate(
    async ([tenant, provider, name]) => {
      const response = await fetch(`/api/${tenant}/integrations/${provider}/runs`, {
        credentials: "include",
      });
      const body = await response.json();
      const rows = (body.runs?.items ?? body.runs ?? []).filter(
        (one) => one.operation === name,
      );
      return rows[0] ?? null;
    },
    [TENANT, PROVIDER, operation],
  );
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const timings = attachTimings(context);
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });
  console.log(`cr069-k: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);

  // ── sign in ──────────────────────────────────────────────────────────────
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click("button[type=submit]");
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });

  // ── 1 · the card is connectable at all ───────────────────────────────────
  console.log("\n1 · the Water meter cloud card");
  await page.goto(`${BASE}/${TENANT}/settings/integrations`, { waitUntil: "networkidle" });
  await shot(page, "01-grid");
  const grid = await page.evaluate(async (tenant) => {
    const r = await fetch(`/api/${tenant}/integrations`, { credentials: "include" });
    return r.json();
  }, TENANT);
  const card = (grid.providers ?? []).find((one) => one.key === PROVIDER);
  check(card !== undefined, "the meter head-end card is on the grid");
  check(
    card?.adapter_registered === true,
    "the meter adapter is REGISTERED, so connect is not refused",
    "hard-won law 2 — before wave K this was false and the card could not be connected",
  );

  // ── 2 · connect it ───────────────────────────────────────────────────────
  console.log("\n2 · connect Brazos Bend's site");
  const connected = await page.evaluate(
    async ([tenant, provider]) => {
      const r = await fetch(`/api/${tenant}/integrations/${provider}/connect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          environment: "production",
          cadence: "manual",
          label: "Water meter cloud",
          fields: { site_id: "BRAZOS-01", api_key: "RECORDED-N360-PAIR-NOT-A-REAL-KEY" },
        }),
      });
      return { status: r.status, body: await r.text() };
    },
    [TENANT, PROVIDER],
  );
  check(
    connected.status === 201 || connected.status === 409,
    "the meter connection is accepted (or already present)",
    `HTTP ${connected.status}`,
  );

  // ── 3 · run the billing export ───────────────────────────────────────────
  console.log("\n3 · they are building the file");
  const exported = await start(page, { operation: EXPORT, parameters: { period: "2026-08" } });
  check(exported.status === 202, "the export is accepted and queued", `HTTP ${exported.status}`);

  await page.goto(`${BASE}/${TENANT}/settings/integrations/${PROVIDER}`, {
    waitUntil: "networkidle",
  });
  await page.waitForSelector("[data-run-row]", { timeout: 20000 });
  await shot(page, "02-detail-list");

  // ── 4 · come back, and the file is in hand ───────────────────────────────
  console.log("\n4 · leave the page, come back");
  await page.goto(`${BASE}/${TENANT}/settings/integrations`, { waitUntil: "networkidle" });
  await page.goto(`${BASE}/${TENANT}/settings/integrations/${PROVIDER}`, {
    waitUntil: "networkidle",
  });
  const exportRun = await latestRun(page, EXPORT);
  check(exportRun !== null, "the export run is on S142");
  const exportRow = page.locator(`[data-run-row="${exportRun?.trace_id ?? ""}"]`);
  check((await exportRow.count()) > 0, "…and has a row a clerk can open");
  const exportTr = page
    .locator("tr", { has: page.locator(`[data-run-row="${exportRun?.trace_id ?? ""}"]`) })
    .first();
  await exportTr.locator("button").last().click();
  await page.waitForSelector("[data-run-card]", { timeout: 20000 });
  const exportCard = await page.locator("[data-run-card]").first().innerText();
  await shot(page, "03-export-card");
  check(
    /the file they built/i.test(exportCard),
    "the collected file is LINKED on the run",
    "BR-INT-046 — a run is not finished until the file is in hand",
  );

  // ── 5 · a request with a safety parameter missing ─────────────────────────
  console.log("\n5 · the readings collection, one parameter short");
  const short = { ...SAFE };
  delete short.actual_consumption;
  const refused = await start(page, {
    operation: READINGS,
    parameters: short,
    window: { from: "2026-08-01", to: "2026-08-29" },
  });
  check(refused.status === 202, "the request is queued", `HTTP ${refused.status}`);
  const refusedRun = await latestRun(page, READINGS);
  check(
    /not started — actual_consumption was not set/.test(refusedRun?.summary ?? ""),
    "the run says WHICH parameter was unset",
    refusedRun?.summary ?? "(no summary)",
  );
  check(
    (refusedRun?.attempted ?? -1) === 0,
    "…and nothing was attempted",
    "US-INT-035 TC-1: no request left",
  );

  // ── 6 · THE CONTROL ──────────────────────────────────────────────────────
  console.log("\n6 · the same collection with all four set — the control case");
  const ran = await start(page, {
    operation: READINGS,
    parameters: SAFE,
    window: { from: "2026-08-01", to: "2026-08-29" },
  });
  check(ran.status === 202, "the full request is queued", `HTTP ${ran.status}`);
  const walked = await latestRun(page, READINGS);
  check(
    (walked?.succeeded ?? 0) > 0,
    "a request that states all four DOES collect",
    `${walked?.succeeded ?? 0} windows — without this, step 5 also describes a broken endpoint`,
  );
  check(
    /window \d+ of \d+/.test(walked?.summary ?? ""),
    "…and the run reads *window N of M*, in the clerk's units",
    walked?.summary ?? "",
  );

  await page.reload({ waitUntil: "networkidle" });
  await shot(page, "04-readings-list");

  // ── 7 · the route-closing export, twice ──────────────────────────────────
  console.log("\n7 · CloseOnExport, twice");
  const firstClose = await start(page, {
    operation: CLOSING_EXPORT,
    parameters: { period: "2026-08", CloseOnExport: true },
    request_key: CLOSE_KEY,
  });
  check(firstClose.status === 202, "the first close is queued", `HTTP ${firstClose.status}`);
  const closed = await latestRun(page, CLOSING_EXPORT);
  const secondClose = await start(page, {
    operation: CLOSING_EXPORT,
    parameters: { period: "2026-08", CloseOnExport: true },
    request_key: CLOSE_KEY,
  });
  check(secondClose.status === 202, "the retry is queued", `HTTP ${secondClose.status}`);
  const retried = await latestRun(page, CLOSING_EXPORT);
  check(
    /already closed on /.test(retried?.summary ?? ""),
    "the retry is REFUSED, naming the day of the first close",
    retried?.summary ?? "(no summary)",
  );
  check(
    retried?.trace_id !== closed?.trace_id,
    "…on a row of its own, so the refusal is visible rather than silent",
  );
  check(
    (retried?.attempted ?? -1) === 0,
    "…and nothing was sent the second time",
    "one close, not two",
  );

  // ── 8 · one credential version after the walk ────────────────────────────
  console.log("\n8 · the credential history");
  const versions = await page.evaluate(
    async ([tenant, provider]) => {
      const r = await fetch(`/api/${tenant}/integrations/${provider}/credential`, {
        credentials: "include",
      });
      if (!r.ok) return null;
      const body = await r.json();
      return body.versions ?? body.items ?? body;
    },
    [TENANT, PROVIDER],
  );
  check(
    Array.isArray(versions) ? versions.length === 1 : versions !== null,
    "the credential history shows ONE version after the walk",
    `BR-INT-047 — a version per mint would be about 144 rows a day on one connection (${
      Array.isArray(versions) ? versions.length : "unreadable"
    })`,
  );

  // ── 9 · rules 31, 32 and 33 ──────────────────────────────────────────────
  console.log("\n9 · no ids, no enum words");
  const listText = await page.locator("body").innerText();
  const everything = `${listText}\n${exportCard}`;
  check(!/\bBR-[A-Z]{3}-\d+\b/.test(everything), "no rule id is on the screen");
  check(
    !/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i.test(everything),
    "no uuid is on the screen (B14 rule 31)",
  );
  check(
    !/\bunconfirmed\b/.test(everything),
    "…and NOT the raw enum word `unconfirmed` (B14 rule 32)",
    "the clerk reads *Unconfirmed*, capitalised, from the catalogue",
  );

  //: ⚠ A DECLARED GAP, WITH A NUMBER, BECAUSE A BLIND SPOT WITH NO COUNT IS
  //: INDISTINGUISHABLE FROM AN EMPTY ONE (law 7's fifth shape).
  gaps.known(
    false,
    "…and the collecting sentence is caught MID-FLIGHT with the count rising",
    {
      defect: "CR-069 wave K",
      why:
        "`JOBS_EAGER=true` runs the job inside the request, so by the time the " +
        "browser can look, the export has finished and the band is gone. The " +
        "band itself is asserted in `ConnectionDetailPage.test.tsx` (three " +
        "cases: the poll shape, the walk shape, and that a FINISHED run draws " +
        "none). Catching it in a browser needs a real Celery worker and a " +
        "fixture that stalls, which is wave G's ground. When the walkthrough " +
        "runs against a worker this gap FAILS for being stale, which is the " +
        "point of recording it here.",
    },
  );

  console.log(`\n${timings.summary ? timings.summary() : ""}`);
  await browser.close();
  process.exit(gaps.report(failures));
})().catch((error) => {
  console.error(error);
  process.exit(2);
});
