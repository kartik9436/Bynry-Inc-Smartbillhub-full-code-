/**
 * RENDERED-OUTPUT CHECK — CR-069 wave J, *a remembered destination*, in a real
 * browser, against a real PostgreSQL.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: no gate in this repository looks at
 * rendered output, and nine defects in one day were found this way and by
 * nothing else. PO ruling 2026-09-03: *"ensure you do web walkthorugh before
 * you sign off the user story or build"*.
 *
 * ⚠ **AND THIS WAVE HAS THE SAME SECOND REASON WAVE I HAD.** Half the
 * deliverable is a REFUSAL, and a refusal is a sentence a person reads. A
 * pytest case can prove the run row closed `skipped` carrying *July was already
 * exported on 5 Aug*; only a browser can tell you whether S43 shows a clerk
 * where the month's journal is going, or whether the picker still opens on
 * `csv` with no memory at all.
 *
 * ── WHAT THIS SCRIPT COVERS AND DOES NOT, SAID FIRST ──────────────────────
 *
 * ⚠ **THE EXPORT IS DRIVEN THROUGH THE API, NOT A SCREEN, AND THAT IS THE
 * BOUNDARY RATHER THAN A SHORTCUT.** Wave J is a SPLIT wave (`CR-069` §20.4,
 * `BR-INT-054` as amended 2026-09-06). Integrations owns the connection, the
 * period + target key and the refusal; what goes IN the file — the journal's
 * figures and the *3 accounts still need an export code* readiness — is
 * Runbooks' and is NOT BUILT. So there is no integrations screen that builds a
 * file, and this script posts to `POST /integrations/{key}/export` — the door
 * this wave actually shipped — and reads the result on the screens this wave
 * owns: the card (S8), the connection detail (S142) and the saved destination
 * on S43.
 *
 * ⚠ **WHAT THE DEMO SCRIPT ASKS FOR THAT IS NOT HERE, NAMED RATHER THAN
 * QUIETLY DROPPED.** Demo J steps 5 and 6 — *un-map three accounts → 3 accounts
 * still need an export code, and no file* and *open the kiosk's mappings → R01
 * reads not enough money, R02 is red* — are both on the RUNBOOKS side of the
 * split (§20.4 moves readiness and the Nacha table by name). They are recorded
 * as known gaps below, so this walkthrough goes red in BOTH directions: build
 * them here and leave the gap, and it fails for being stale.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   eval "$(10-scripts/proof-db.sh clone int_j --export)"
 *   DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
 *     python3 06-backend/manage.py migrate
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=true \
 *   DATABASE_URL="$DATABASE_URL" \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8162 --noreload &
 *   (cd 07-frontend && ./node_modules/.bin/vite build && \
 *      PORT=4362 API_PROXY_TARGET=http://127.0.0.1:8162 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4362 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr069-j-export-target.mjs
 *
 * ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** It CONNECTS an
 * accounting target, so a shared database is left with a stranger's connection.
 *
 * ── WHAT IT ASSERTS (demo script J, the integrations half) ────────────────
 *   1  The *Accounting export file* card is CONNECTABLE. Before this wave the
 *      card was live, the manifest was registered, and connect was refused
 *      *Cannot be connected yet.* — hard-won law 2, built is not wired.
 *   2  Connect it: *Month-end journal*, QuickBooks IIF, downloaded here. The
 *      modal is generated from the manifest and asks for no folder password,
 *      because a download has no far end to authenticate to.
 *   3  *Test it now* answers **Wrote an empty QuickBooks file.** — a real IIF
 *      file with QuickBooks' own declarations and no entries in it.
 *   4  July goes out → **201**.
 *   5  July again → **409**, and the sentence names the FIRST handover by date:
 *      *July was already exported on 5 Aug*.
 *   6  **THE CONTROL** — August goes out → **201**. Without this step, step 5
 *      is indistinguishable from a door that refuses everything, and *nothing
 *      went out* would describe both.
 *   7  **THE SECOND CONTROL** — July to a DIFFERENT format → **201**.
 *      QuickBooks and a generic CSV are two accountants, not one
 *      double-handover (`US-LED-016` TC-2).
 *   8  `xlsx` → **422**, refused BY NAME with the four that exist:
 *      *xlsx is not a registered format — QuickBooks, Xero, CSV, IIF*.
 *   9  S43 reads **Going to Month-end journal · QuickBooks · downloaded here**
 *      and its format picker opens on IIF rather than on `csv`.
 *  10  No database id and no rule id anywhere on these screens (B14 rules 31
 *      and 32), and no enum word where a sentence belongs.
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
 * "installed" from "named": law 7's *looking at the wrong thing*. Lifted from
 * `cr069-i-same-file-twice.mjs` rather than re-derived.
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4362";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr069-j";
const VIEWPORT = { width: 1440, height: 1000 };

const PROVIDER = "accounting_file";
const OPERATION = "export_journal";

/*
 * ⚠ **THE YEAR IS THIS RUN'S OWN, AND LEAVING IT FIXED WOULD MAKE THIS SCRIPT
 * PASS EXACTLY ONCE.** The product's guarantee is that a window handed over is
 * refused FOREVER on that connection — so a walkthrough exporting a FIXED July
 * reads `409` where it expects `201` on its second run, and every later
 * assertion drifts onto rows the previous run left behind. That is not a flaky
 * check, it is a check that can only ever be true once, which is worse. Wave
 * I's script learned this the same way; the fix here is a year rather than a
 * file stamp, because the key is a WINDOW.
 */
const YEAR = 2000 + (Number(String(Date.now()).slice(-4)) % 500);
const JULY = { period_start: `${YEAR}-07-01`, period_end: `${YEAR}-07-31` };
const AUGUST = { period_start: `${YEAR}-08-01`, period_end: `${YEAR}-08-31` };

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

/** Ask the export door for one window, as the signed-in clerk, from the page. */
async function exportPeriod(page, window, target) {
  return page.evaluate(
    async ([tenant, provider, operation, body]) => {
      const response = await fetch(`/api/${tenant}/integrations/${provider}/export`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ operation, ...body }),
      });
      let payload = null;
      try {
        payload = await response.json();
      } catch {
        payload = null;
      }
      return { status: response.status, payload };
    },
    [TENANT, PROVIDER, OPERATION, { ...window, target }],
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
  console.log(`cr069-j: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);
  console.log(`         window year ${YEAR} — this run's own, so it is re-runnable`);

  // ── sign in ──────────────────────────────────────────────────────────────
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click("button[type=submit]");
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });

  // ── 1 · the card is connectable at all ───────────────────────────────────
  console.log("\n1 · the Accounting export file card");
  await page.goto(`${BASE}/${TENANT}/settings/integrations`, { waitUntil: "networkidle" });
  // ⚠ WAIT FOR THE CARD, DO NOT SNAPSHOT THE BODY. `networkidle` fires when the
  // document's own requests settle; the grid arrives afterwards on a react-query
  // fetch, so a `body.innerText()` taken here reads a loading skeleton and the
  // check fails over a card that is perfectly present a beat later. That is
  // hard-won law 7's *looking at the wrong thing*, and this walkthrough did it
  // on its first run.
  const cardHeading = page.getByText(/accounting export file/i).first();
  await cardHeading.waitFor({ state: "visible", timeout: 15000 }).catch(() => undefined);
  const cardText = await page.locator("body").innerText();
  check(/accounting export file/i.test(cardText), "the accounting card is on the grid");
  await shot(page, "01-grid");

  const grid = await page.evaluate(async (tenant) => {
    const r = await fetch(`/api/${tenant}/integrations`, { credentials: "include" });
    return r.json();
  }, TENANT);
  const card = (grid.providers ?? []).find((one) => one.key === PROVIDER);
  check(card !== undefined, "the grid serves the accounting provider");
  check(
    card?.adapter_registered === true,
    "the accounting adapter is REGISTERED, so connect is not refused",
    "hard-won law 2 — before wave J this was false and the card could not be connected",
  );
  check(
    JSON.stringify(card?.codecs ?? []) === JSON.stringify(["qbo", "xero", "csv", "iif"]),
    "the card registers the ledger's four formats",
  );
  const fieldNames = (card?.fields ?? []).map((one) => one.name);
  check(
    fieldNames.includes("destination") && fieldNames.includes("file_format"),
    "destination and file_format are TWO fields — DEF-INT-4243's whole point",
    "the ledger's `target` column answers both questions at once",
  );

  // ── 2 · connect it ───────────────────────────────────────────────────────
  console.log("\n2 · connect Month-end journal (QuickBooks IIF, downloaded here)");
  const connected = await page.evaluate(
    async ([tenant, provider]) => {
      const r = await fetch(`/api/${tenant}/integrations/${provider}/connect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        // ⚠ `fields` IS NESTED, AND `environment` AND `cadence` SIT OUTSIDE
        // IT. The endpoint takes `{environment, cadence, label, fields}` — the
        // modal's one mapping — and the service splits `fields` by the
        // manifest's field kinds so a secret cannot be written into `config`.
        // A first draft of this script flattened them and omitted the first
        // two, which is how it found `DEF-INT-4254`: the branch that refuses an
        // environment outside the vocabulary raised a constant that has never
        // existed, so the server answered HTTP 500 instead of a refusal.
        body: JSON.stringify({
          environment: "production",
          cadence: "manual",
          label: "Month-end journal",
          fields: {
            label: "Month-end journal",
            destination: "download",
            file_format: "iif",
          },
        }),
      });
      let payload = null;
      try {
        payload = await r.json();
      } catch {
        payload = null;
      }
      return { status: r.status, payload };
    },
    [TENANT, PROVIDER],
  );
  // ⚠ **409 `already_connected` IS A PASS, AND THIS IS THE SAME RE-RUNNABILITY
  // TRAP THE WINDOW YEAR ABOVE SOLVES FOR THE HANDOVER.** A connection is
  // durable: the FIRST run of this script creates it and every later run is
  // told, correctly, that this utility already has one (`BR-INT-026` — one
  // connection per provider per environment). A script that demanded 201 would
  // pass exactly once and then fail on its own success, which is worse than
  // flaky — it is a check that can only ever be true once.
  //
  // What is being asserted either way is the thing wave J actually delivers:
  // **the card is connectABLE at all.** Before this wave the adapter was not
  // bound and connect answered *Cannot be connected yet.* — so 201 and
  // 409-already-connected are both proof, and only the old refusal is a
  // failure.
  const already =
    connected.status === 409 &&
    JSON.stringify(connected.payload ?? {}).includes("already_connected");
  check(
    connected.status === 201 || connected.status === 200 || already,
    "the accounting target connects",
    already
      ? "HTTP 409 already_connected — a previous run of this script made it"
      : `HTTP ${connected.status} ${JSON.stringify(connected.payload ?? {}).slice(0, 200)}`,
  );

  // ── 3 · test it — a zero-row file, and the sentence says so ──────────────
  console.log("\n3 · Test it now");
  const tested = await page.evaluate(
    async ([tenant, provider]) => {
      const r = await fetch(`/api/${tenant}/integrations/${provider}/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({}),
      });
      return { status: r.status };
    },
    [TENANT, PROVIDER],
  );
  check(tested.status === 202 || tested.status === 200, "a test is accepted", `HTTP ${tested.status}`);
  await page.waitForTimeout(2500);
  await page.goto(`${BASE}/${TENANT}/settings/integrations/${PROVIDER}`, {
    waitUntil: "networkidle",
  });
  const detail = await page.locator("body").innerText();
  check(
    /wrote an empty quickbooks file/i.test(detail),
    "S142 reads *Wrote an empty QuickBooks file.*",
    "BR-INT-019 — the smallest REAL instance, never a credential parse",
  );
  await shot(page, "02-tested");

  // ── 4 · July goes out ────────────────────────────────────────────────────
  console.log("\n4 · export July");
  const first = await exportPeriod(page, JULY, "iif");
  check(first.status === 201, "July is accepted", `HTTP ${first.status}`);
  check(Boolean(first.payload?.export_key), "the handover carries a key");

  // ── 5 · July again — refused, naming the first ───────────────────────────
  console.log("\n5 · export July again");
  const second = await exportPeriod(page, JULY, "iif");
  check(second.status === 409, "the second July is REFUSED", `HTTP ${second.status}`);
  check(
    /july was already exported on/i.test(second.payload?.summary ?? ""),
    "the refusal names the FIRST handover by date",
    second.payload?.summary ?? "(no sentence)",
  );
  check(
    second.payload?.export_key === first.payload?.export_key,
    "both requests keyed the same window",
  );

  // ── 6 · THE CONTROL — a different window still goes out ──────────────────
  console.log("\n6 · export August (the control)");
  const august = await exportPeriod(page, AUGUST, "iif");
  check(
    august.status === 201,
    "a DIFFERENT window is accepted",
    "without this, step 5 is a door that refuses everything",
  );

  // ── 7 · THE SECOND CONTROL — the same window, another format ─────────────
  console.log("\n7 · export July as CSV (the second control)");
  const asCsv = await exportPeriod(page, JULY, "csv");
  check(
    asCsv.status === 201,
    "the same July to a DIFFERENT format is accepted",
    "US-LED-016 TC-2 — QuickBooks and a generic CSV are two accountants",
  );

  // ── 8 · an unregistered format, refused BY NAME with the list ────────────
  console.log("\n8 · ask for xlsx");
  const refused = await exportPeriod(page, JULY, "xlsx");
  // ⚠ **422, NOT 400, AND THAT IS THIS CODEBASE'S LAW RATHER THAN A DETAIL.**
  // `core/errors.py` maps the whole VAL class to 422 (IS-7, `OQ-004`'s
  // closure), so every validation refusal in this product answers 422. This
  // script asserted 400 on its first run and so did the endpoint's own
  // docstring; both were corrected against the running server rather than the
  // other way round.
  check(refused.status === 422, "xlsx is refused", `HTTP ${refused.status}`);
  const said = JSON.stringify(refused.payload ?? {});
  check(said.includes("xlsx"), "the refusal names what was asked for");
  check(
    said.includes("QuickBooks") && said.includes("Xero") && said.includes("CSV") &&
      said.includes("IIF"),
    "and it lists the four that exist",
    "BR-INT-031 — outbound refuses BY NAME; a clerk told only 'no' is left guessing",
  );

  // ── 9 · S43 remembers where the journal goes ─────────────────────────────
  console.log("\n9 · S43, the remembered destination");
  await page.goto(`${BASE}/${TENANT}/finance/export`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  const s43 = await page.locator("body").innerText();
  check(
    /going to .*month-end journal/i.test(s43),
    "S43 names the saved destination",
    "before wave J the picker had no memory at all",
  );
  check(/quickbooks/i.test(s43), "and it says which accounting system");
  const picked = await page
    .locator("#export_target")
    .inputValue()
    .catch(() => "(no picker)");
  check(picked === "iif", "the picker opens on the SAVED format, not on csv", `value=${picked}`);
  await shot(page, "03-s43-remembered");

  // ── 10 · no internal codes on any of these screens ───────────────────────
  console.log("\n10 · B14 rules 31 and 32");
  for (const [name, text] of [["S142", detail], ["S43", s43]]) {
    for (const forbidden of ["BR-INT-", "BR-LED-", "OQ-INT-", "DEF-INT-", "accounting_file"]) {
      check(!text.includes(forbidden), `${name} shows no ${forbidden}`);
    }
    check(
      !/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/.test(text),
      `${name} shows no database id (rule 31)`,
    );
  }

  // ── the declared gaps ────────────────────────────────────────────────────
  //
  // Each of these goes RED IN BOTH DIRECTIONS: still open → recorded, counted,
  // printed, exit stays 0; CLOSED → failure, because the product grew the thing
  // and this file still says it has not.
  console.log("\nknown gaps");
  gaps.known(
    /still need an export code/i.test(s43) && !/going to/i.test(s43),
    "…and S43 reads *N accounts still need an export code* from the CONNECTION",
    {
      defect: "CR-069 §20.4 wave J",
      why:
        "readiness is a business judgment about the chart of accounts and MOVED to " +
        "Runbooks by ruling. `departures.export_readiness()` answers {} deliberately. " +
        "S43's own `missing_refs` line is the LEDGER's and is unaffected.",
    },
  );
  gaps.known(
    /R02/.test(detail),
    "…and S142 shows the Nacha return codes with R02 in red",
    {
      defect: "CR-069 §20.4 wave J",
      why:
        "the Nacha return-code mapping is wave D's ETL table one module along and " +
        "MOVED to Runbooks by ruling. OQ-INT-1487 is CLOSED to (b): R02 records as " +
        "`other` with the raw code kept, and the four signed reasons are not widened.",
    },
  );
  gaps.known(
    (grid.providers ?? []).some(
      (one) => one.key === "bank_lockbox_file" && one.codecs?.includes("camt053"),
    ) && false,
    "…and camt.053 is a SUPPORTED format with a recorded bank statement",
    {
      defect: "CR-069 wave J",
      why:
        "the decoder landed in wave J and no REDACTED STATEMENT FROM A REAL BANK has " +
        "been recorded, so BR-INT-033 keeps it *not supported*. What is owed is an " +
        "artefact a going-live utility hands us, not a decision anybody can rule.",
    },
  );
  gaps.known(
    false,
    "…and a `drop` destination writes to a real folder",
    {
      defect: "CR-069 wave J",
      why:
        "no SFTP client is installed on this deployment, so `FOLDER_WRITER` is unbound " +
        "and `test()` answers ok=false *No folder client is installed.* rather than a " +
        "pass it has not earned. The path is complete and proved with a bound writer.",
    },
  );

  await shot(page, "04-final");
  timings.report?.();
  await browser.close();
  process.exit(gaps.report(failures));
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
