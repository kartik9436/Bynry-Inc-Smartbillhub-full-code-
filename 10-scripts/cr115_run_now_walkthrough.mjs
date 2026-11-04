/**
 * ── Trace ──────────────────────────────────────────────
 * Change:  CR-115-BRC05 R31 (2.292.0) — *"i dont have Run button here"*. The
 *          parcel reconciliation gets a door: Preview and Apply, on the
 *          operation's own row, and a report a clerk can read.
 * Screens: S142 the connector view — `/:tenant/settings/integrations/gis_esri`
 *          (`features/integrations/ConnectionDetailPage.tsx`)
 * Rules:   BR-INT-074 (a PREVIEW writes nothing that is being reconciled) ·
 *          BR-INT-039 (every attempt is a durable record — a preview too) ·
 *          B14 rule 2 + the ratified header set (Edit · Keys · Disconnect ·
 *          Regenerate, 2026-09-17) — *Run now* must not become a fifth ·
 *          PO ruling R28 *"(c) never touch by default"* · hard-won law 2
 *          (built is not wired — `DEF-INT-5601`) · law 6 (no gate in this repo
 *          reads rendered output) · law 7 (a check must tell PASS from FAIL to
 *          a reader, and must name what would make it pass wrongly)
 * ───────────────────────────────────────────────────────
 *
 * ⚠⚠ **THIS WALK PROVES OUR CODE. IT PROVES NOTHING ABOUT ANN ARBOR'S DATA.**
 * The egress proxy in this environment refuses `a2mapseg.a2gov.org` — `curl`
 * returns code `000` and Django sees `Tunnel connection failed: 403 Forbidden`.
 * Not one byte of the City's register has ever been read here. The layer this
 * walk reads is `apps/integrations/gis_esri_fixtures.py`, whose own docstring
 * says in its first paragraph that it is **constructed, not recorded** — the
 * ArcGIS REST protocol shaped by hand from documented field names. A green run
 * means our pull, our match, our two modes and our report behave. It does NOT
 * mean the Ann Arbor integration works.
 *
 * RUN IT (the smoke stack's shape — the vite dev server has no /api proxy):
 *     DATABASE_URL="postgres://…/sbh_lane2?sslmode=disable" \
 *     DJANGO_SETTINGS_MODULE=config.settings.local \
 *     PYTHON="$PWD/06-backend/.venv/bin/python" \
 *     SMOKE_API_PORT=8002 SMOKE_WEB_PORT=8082 SMOKE_SKIP_SEED=1 \
 *     ./10-scripts/11-smoke-stack.sh
 *     BASE=http://127.0.0.1:8082 PGURL="…" node 10-scripts/cr115_run_now_walkthrough.mjs
 *
 * ⚠ **STEP 0 PRINTS THE BUNDLE AND THE BACKEND IT DROVE.** *Which build am I
 * looking at* is the question this CR has already got wrong twice, and a
 * browser proof that cannot name what it drove proves nothing.
 *
 * ⚠ **IT REPOINTS THE TENANT'S `gis_esri` `base_url` AT THE RECORDED LAYER AND
 * PUTS THE ORIGINAL BACK IN A `finally`**, printing both and FAILING LOUDLY if
 * they differ at the end. The seeded value is `https://gis.brazosbend.example/addr`,
 * which is the ADDRESS-SEARCH fixture's host and serves `{"candidates": […]}`
 * to any URL — so a walk that did not repoint would read a metadata document
 * with no `maxRecordCount` in it and see the run refuse, for ever, on every
 * reserved host. That went wrong once in code and is why `gis._layer_transport`
 * exists.
 *
 * ── WHAT WOULD MAKE EACH STEP PASS WRONGLY (law 7, habit 2) ────────────────
 *  1 THE CONTROL EXISTS — the word *Run* appears on this screen in the shell's
 *    *Runbooks* nav item and in the run-history table's own words. Matching
 *    `/run/i` over the body passes in both directions. So every assertion here
 *    addresses `[data-run-now="reconcile_parcels"]`, `[data-run-preview]` and
 *    `[data-run-apply]` — attributes that exist for no other reason.
 *  2 IT IS ON THE RIGHT ROW — a control rendered ONCE somewhere on the page
 *    satisfies a page-wide count. So the Run cell is read PER `data-operation`
 *    row and the other two rows are asserted EMPTY, which is the half that
 *    says the server's `can_run_now` is being obeyed rather than ignored.
 *  3 IT DID NOT BECOME A FIFTH HEADER ACTION — counting buttons in the header
 *    would count the two new ones if they had leaked there. So the header's
 *    own controls are read by the attributes the ratified four already carry
 *    (`data-edit`, `data-keys-link`, `data-disconnect`, `data-regenerate-key`)
 *    AND the header subtree is asserted to contain NO `[data-run-preview]`.
 *  4 PREVIEW WROTE NOTHING — the SCREEN cannot answer this: it draws what the
 *    response said. And `applied: {}` is the server's own claim about itself.
 *    So the rows are counted in PostgreSQL, under `app.tenant_id`, BEFORE and
 *    AFTER, and compared. ⚠ Without the tenant GUC every count is ZERO under
 *    RLS FORCE and *nothing changed* would be true of an empty answer as much
 *    as of an untouched one — law 7's *reporting zero over a scope it silently
 *    excludes*, which would make this the weakest step rather than the point.
 *  5 THE REPORT IS HONEST — *0 differences found, 0 applied* over a clean
 *    estate and over a button that did nothing look identical. So the report
 *    must also state what it EXAMINED, and this step reads that figure.
 *  6 THE RUN IS RECORDED — a run row could exist and carry no mode. So this
 *    reads `integration_run.mode` and `started_by_name` out of PostgreSQL,
 *    not off the screen.
 */
import { createRequire } from "node:module";
import { execFileSync } from "node:child_process";
import { mkdirSync, existsSync, readdirSync } from "node:fs";
import { join } from "node:path";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url).pathname);
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8082";
const T = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const PGURL =
  process.env.PGURL ??
  "postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_lane2?sslmode=disable";
const OUT = process.env.OUT ?? "/tmp/cr115-run-now";
/** The recorded Esri layer — `gis_esri_fixtures.FIXTURE_LAYER`. NOT Ann Arbor. */
const FIXTURE_LAYER =
  "https://gis.example/arcgis/rest/services/Qualified/FeatureServer/0";
mkdirSync(OUT, { recursive: true });

function chrome() {
  const want = chromium.executablePath();
  if (want && existsSync(want)) return want;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const d of readdirSync(root)) {
      const c = join(root, d, "chrome-linux", "chrome");
      if (existsSync(c)) return c;
    }
  }
  throw new Error("no chromium — set PLAYWRIGHT_BROWSERS_PATH (never run `playwright install`)");
}

// ⚠ `psql -tAc "set …; select …"` PRINTS THE `SET` COMMAND TAG ON ITS OWN LINE
// and `-tA` does not suppress it. Dropped here once rather than at each call.
const raw = (q) =>
  execFileSync("psql", [PGURL, "-tAc", q], { encoding: "utf8" })
    .split("\n")
    .filter((line) => line.trim() !== "SET" && line.trim() !== "UPDATE 1")
    .join("\n")
    .trim();
let TENANT_ID = "";
const sql = (q) => raw(`set app.tenant_id='${TENANT_ID}'; ${q}`);

let fails = 0;
const say = (label, ok, detail = "") => (
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${label}${detail ? " — " + detail : ""}`), ok || fails++
);

/** Everything a reconciliation run could touch, counted the way a person would. */
const rowCounts = () =>
  sql(
    `select
       (select count(*) from premises),
       (select count(*) from units),
       (select count(*) from premises where gis_parcel_id is not null),
       (select count(*) from units where gis_point_id is not null),
       (select count(*) from premises where gis_verified),
       (select count(*) from units where gis_verified),
       (select coalesce(md5(string_agg(p.id::text || coalesce(p.address_line,'') ||
          coalesce(p.city,'') || coalesce(p.gis_parcel_id,'') || p.gis_verified::text,
          '|' order by p.id)), 'empty') from premises p)`,
  );

let savedBaseUrl = null, borrowed = false;
/** The one premises this walk renames so a match is possible at all, and the
 *  address it held before. Put back in the `finally`, printed both ways. */
let matchRow = null, savedAddress = null;
/** `gis_esri_fixtures.FEATURES[0]` — a house, one point, no unit. Chosen because
 *  it is the branch where a PREMISES takes both a parcel key and a pin. */
const FIXTURE_STREET = "100 N Maple St";
const FIXTURE_PIN = "09-01-100";

(async () => {
  console.log("CR-115-BRC05 R31 — RUN NOW, walked in a browser");
  console.log("⚠ THE CITY IS A RECORDED FIXTURE, NOT ANN ARBOR. See this file's banner.\n");

  // ── 0 · WHICH BUILD, WHICH BACKEND ──────────────────────────────────────
  console.log("0 · WHAT THIS RUN DROVE");
  TENANT_ID = raw(`select id from tenants where subdomain='${T}'`);
  say("the tenant resolves", TENANT_ID.length > 10, TENANT_ID);
  const version = raw(`select 1`) && JSON.parse(
    execFileSync("node", ["-e", `process.stdout.write(JSON.stringify(require("${new URL("../07-frontend/package.json", import.meta.url).pathname}")))`], { encoding: "utf8" }),
  ).version;
  console.log(`  >> SPA  ${BASE}  (package.json version ${version})`);
  const health = await fetch(`${BASE}/api/${T}/health`).then((r) => r.status).catch(() => "no answer");
  console.log(`  >> API  behind ${BASE}/api  (health → ${health})`);

  savedBaseUrl = sql(
    `select config->>'base_url' from integration_connection where provider_key='gis_esri'`,
  );
  console.log(`  >> connector base_url BEFORE: ${savedBaseUrl}`);
  sql(
    `update integration_connection set config = jsonb_set(config,'{base_url}',to_jsonb('${FIXTURE_LAYER}'::text))
       where provider_key='gis_esri'`,
  );
  borrowed = true;
  console.log(`  >> BORROWED: base_url repointed at the RECORDED Esri layer. NOT the City.`);

  const b = await chromium.launch({ executablePath: chrome(), args: ["--no-sandbox"] });
  const p = await b.newPage({ viewport: { width: 1600, height: 1800 } });
  const calls = [];
  p.on("response", async (r) => {
    if (!r.url().includes("/api/")) return;
    if (r.request().method() === "GET") return;
    let body = ""; try { body = await r.text(); } catch { /* streamed */ }
    calls.push({ url: r.url(), status: r.status(), body, sent: r.request().postData() });
  });

  try {
    await p.goto(`${BASE}/${T}/signin`, { waitUntil: "networkidle" });
    await p.fill("#signin-email", EMAIL);
    await p.fill("#signin-password", PASSWORD);
    await p.click('button[type="submit"]');
    await p.waitForTimeout(2500);

    await p.goto(`${BASE}/${T}/settings/integrations/gis_esri`, { waitUntil: "networkidle" });
    await p.waitForTimeout(2000);
    await p.screenshot({ path: `${OUT}/00-screen.png`, fullPage: true });

    // ── 1 · THE CONTROL EXISTS, AND ON THE RIGHT ROW ──────────────────────
    console.log("\n1 · WHERE THE CONTROL LIVES");
    say(
      "the API table draws a RUN column header",
      (await p.locator("th", { hasText: /^Run$/ }).count()) === 1,
    );
    const onReconcile = await p.locator('[data-run-now="reconcile_parcels"]').count();
    say("the reconcile row has a Run now control", onReconcile === 1);
    say(
      "it offers TWO buttons, Preview and Apply — never one that does the dangerous thing",
      (await p.locator("[data-run-preview]").count()) === 1 &&
        (await p.locator("[data-run-apply]").count()) === 1,
    );
    for (const other of ["address_search", "map_tiles"]) {
      const cell = p.locator(`[data-run-cell="${other}"]`);
      const text = (await cell.count()) ? (await cell.innerText()).trim() : "<no cell>";
      say(
        `the ${other} row's Run cell is EMPTY (the server says it has no door)`,
        (await cell.count()) === 1 && text === "",
        text === "" ? "" : text,
      );
    }

    // ── 2 · IT DID NOT BECOME A FIFTH HEADER ACTION (B14 rule 2) ──────────
    console.log("\n2 · THE RATIFIED HEADER SET IS UNCHANGED");
    const head = p.locator("header").first();
    const headHasRun = (await head.locator("[data-run-preview], [data-run-apply]").count()) > 0;
    say("no Run control leaked into the page header", headHasRun === false);
    const ratified = [];
    for (const [name, sel] of [
      ["Edit", "[data-edit]"],
      ["Keys", "[data-keys-link]"],
      ["Disconnect", "[data-disconnect]"],
      ["Regenerate", "[data-regenerate-key]"],
      ["Connect", "[data-connect]"],
      ["Replace password", "[data-replace-password]"],
    ]) if (await p.locator(sel).count()) ratified.push(name);
    console.log(`  >> header actions present: ${ratified.join(" · ") || "(none)"}`);

    // ── 3 · PREVIEW WRITES NOTHING ────────────────────────────────────────
    console.log("\n3 · PREVIEW — THE CENTRAL CLAIM");
    const before = rowCounts();
    console.log(`  >> rows BEFORE (premises|units|keyed p|keyed u|verified p|verified u|digest):\n     ${before}`);
    const writesBefore = calls.length;
    await p.click("[data-run-preview]");
    await p.waitForTimeout(6000);
    await p.screenshot({ path: `${OUT}/01-preview.png`, fullPage: true });
    const preview = calls.slice(writesBefore).find((c) => c.url.includes("/reconcile"));
    say("pressing Preview calls POST …/reconcile", Boolean(preview),
        preview ? `${preview.status} ${preview.sent}` : "no call left the browser");
    say("it answers 200 with the report itself, not 202 with a job id",
        preview?.status === 200, preview ? preview.body.slice(0, 120) : "");
    const after = rowCounts();
    console.log(`  >> rows AFTER:\n     ${after}`);
    say("⚠ NOT ONE ROW MOVED — counted in PostgreSQL under the tenant's own GUC, "
        + "including a digest over every address and key",
        before === after,
        before === after ? "" : `BEFORE ${before} != AFTER ${after}`);
    const report = preview ? JSON.parse(preview.body || "{}") : {};
    say("the server also reports it applied nothing",
        JSON.stringify(report.applied ?? {}) === "{}", JSON.stringify(report.applied));

    // ── 4 · THE REPORT A CLERK READS ──────────────────────────────────────
    console.log("\n4 · WHAT THE CLERK IS TOLD");
    const panel = p.locator("[data-reconcile-result]");
    say("a result panel appears under the table", (await panel.count()) === 1);
    const headline = (await p.locator("[data-reconcile-headline]").count())
      ? (await p.locator("[data-reconcile-headline]").innerText()).trim() : "";
    console.log(`  >> headline: ${headline}`);
    say("it says how many differences and how many were applied", /\d/.test(headline));
    say("R28 — *0 applied* carries its REASON, or a clerk files a defect against correct behaviour",
        (await p.locator("[data-reconcile-never-touch]").count()) === 1,
        `fields_set_to_never_touch=${report.counts?.fields_set_to_never_touch}`);
    say("the panel says in words that a preview wrote nothing",
        (await p.locator("[data-reconcile-preview-only]").count()) === 1);
    const examined = await p.locator('[data-reconcile-count="examined"]').innerText().catch(() => "");
    const cityRows = await p.locator('[data-reconcile-count="cityRows"]').innerText().catch(() => "");
    say("⚠ it states what it EXAMINED beside what differed — otherwise a clean estate "
        + "and a dead button read identically",
        examined !== "" && cityRows !== "", `city rows ${cityRows}, ours examined ${examined}`);

    // ── 5 · THE RUN IS A DURABLE RECORD, WITH ITS MODE AND ITS PERSON ─────
    console.log("\n5 · WHAT THE RUN ROW HOLDS (read from PostgreSQL, not the screen)");
    const row = sql(
      `select mode, started_by_name, trigger, operation, outcome, summary
         from integration_run
        where operation='reconcile_parcels'
        order by started_at desc limit 1`,
    );
    console.log(`  >> ${row}`);
    const [mode, who, trigger, operation] = row.split("|");
    say("the run recorded its MODE", mode === "preview", mode);
    say("it recorded WHICH person started it", (who ?? "").trim().length > 0, who);
    say("`trigger` already carries the schedule-or-a-person half", trigger === "manual", trigger);
    say("it is recorded against the operation the button names", operation === "reconcile_parcels");

    // ── 6 · APPLY IS THE ONLY THING THAT WRITES ───────────────────────────
    console.log("\n6 · APPLY — BEHIND A CONFIRM, AND THE ONLY WRITER");
    const writes2 = calls.length;
    await p.click("[data-run-apply]");
    await p.waitForTimeout(1200);
    await p.screenshot({ path: `${OUT}/02-confirm.png`, fullPage: true });
    say("Apply opens a confirm rather than running",
        calls.slice(writes2).every((c) => !c.url.includes("/reconcile")));
    const dialog = p.getByRole("alertdialog");
    say("the confirm states the consequence before the act",
        (await dialog.count()) > 0 &&
          /writes to your properties/i.test(await dialog.first().innerText()));
    await dialog.getByRole("button", { name: /^Apply$/ }).last().click();
    await p.waitForTimeout(8000);
    await p.screenshot({ path: `${OUT}/03-applied.png`, fullPage: true });
    const applied = calls.slice(writes2).find((c) => c.url.includes("/reconcile"));
    say("confirming calls POST …/reconcile with mode=apply", applied?.sent?.includes("apply"),
        applied ? `${applied.status} ${applied.sent}` : "no call");
    const applyReport = applied ? JSON.parse(applied.body || "{}") : {};
    console.log(`  >> applied: ${JSON.stringify(applyReport.applied)}`);
    console.log(`  >> counts:  ${JSON.stringify(applyReport.counts)}`);
    say("R28 — an APPLY still changes no address field",
        (applyReport.applied?.fields_applied ?? 0) === 0,
        `fields_applied=${applyReport.applied?.fields_applied}`);
    say("and it did not die on row one — `rows_refused` is 0 (`DEF-INT-5629`)",
        (applyReport.applied?.rows_refused ?? 0) === 0,
        `rows_refused=${applyReport.applied?.rows_refused}`);
    const afterApply = rowCounts();
    console.log(`  >> rows AFTER APPLY:\n     ${afterApply}`);
    say("⚠ NOTHING MATCHED, SO NOTHING WAS WRITTEN — and `rows_refused: 0` over ZERO "
        + "attempted rows is law 7's *zero over a scope it excludes*. Step 7 is the real proof.",
        afterApply === after && (applyReport.counts?.differences_found ?? -1) === 0,
        `queued=${applyReport.counts?.queued}, unmatched_ours=${applyReport.counts?.unmatched_ours}`);
    say("the queue link is drawn where there is something to open",
        (await p.locator("[data-reconcile-queue]").count()) === 1,
        `queued=${applyReport.counts?.queued}`);

    // ── 7 · A ROW THAT ACTUALLY MATCHES — THE WRITE PATH, END TO END ──────
    //
    // ⚠ **WITHOUT THIS STEP THE WHOLE APPLY PATH IS UNPROVEN IN A BROWSER.**
    // The seeded estate is in Katy, Texas and the recorded layer is a fictional
    // Riverbend, Michigan, so step 6's apply matched nothing, wrote nothing, and
    // reported `rows_refused: 0` over ZERO attempted rows. That number reads
    // exactly like a healthy write and is a statement about an empty set —
    // hard-won law 7's *reporting zero over a scope it silently excludes*.
    //
    // ⚠ **AND IT IS THE STEP THAT PROVES `DEF-INT-5629`.** Every patch the run
    // builds carried a field metering's validator answered
    // `metering.unknown_field` to, and `ValidationError` is not the
    // `DatabaseError` the savepoint catches, so before that fix this step would
    // not have written a wrong value — it would have taken the whole run down.
    //
    // It renames ONE premises to an address the recorded layer holds, applies,
    // reads the key back out of PostgreSQL, and puts the address back in the
    // `finally` — printing both and FAILING LOUDLY if they differ.
    console.log("\n7 · A MATCHING ROW — DOES AN APPLY ACTUALLY WRITE THE KEY?");
    const target = sql(`select id, address_line from premises order by premise_no limit 1`);
    [matchRow, savedAddress] = target.split("|");
    console.log(`  >> borrowing ${matchRow} — address was "${savedAddress}"`);
    sql(
      `update premises set address_line='${FIXTURE_STREET}', city='Riverbend', state='MI',
              postal_code='48104' where id='${matchRow}'`,
    );
    await p.reload({ waitUntil: "networkidle" });
    await p.waitForTimeout(1500);
    const writes3 = calls.length;
    await p.click("[data-run-apply]");
    await p.waitForTimeout(1200);
    await p.getByRole("alertdialog").getByRole("button", { name: /^Apply$/ }).last().click();
    await p.waitForTimeout(9000);
    await p.screenshot({ path: `${OUT}/04-matched.png`, fullPage: true });
    const matched = calls.slice(writes3).find((c) => c.url.includes("/reconcile"));
    const matchedReport = matched ? JSON.parse(matched.body || "{}") : {};
    console.log(`  >> applied: ${JSON.stringify(matchedReport.applied)}`);
    say("the run found the row this time", (matchedReport.counts?.unmatched_ours ?? 99) < 6,
        `unmatched_ours=${matchedReport.counts?.unmatched_ours}`);
    say("it took a key", (matchedReport.applied?.keys_taken ?? 0) > 0,
        `keys_taken=${matchedReport.applied?.keys_taken}`);
    say("and it refused no row — the seven fields metering used to reject are accepted",
        (matchedReport.applied?.rows_refused ?? 1) === 0,
        `rows_refused=${matchedReport.applied?.rows_refused}`);
    const stored = sql(
      `select gis_parcel_id, gis_verified, gis_verified_at is not null
         from premises where id='${matchRow}'`,
    );
    console.log(`  >> premises row now: ${stored}`);
    say(`⚠ THE KEY IS IN THE COLUMN, read back from PostgreSQL — not off the screen`,
        stored.startsWith(`${FIXTURE_PIN}|t|t`), stored);
    const addressStill = sql(`select address_line from premises where id='${matchRow}'`);
    say("R28 — and the ADDRESS was not touched, because no field is turned on",
        addressStill === FIXTURE_STREET, addressStill);
  } finally {
    await p.context().browser().close().catch(() => {});
    if (matchRow && savedAddress !== null) {
      sql(
        `update premises set address_line='${savedAddress}', city='Katy', state='TX',
                postal_code='77494', gis_parcel_id=null, gis_parcel_id_was=null,
                gis_key_changed_at=null, gis_verified=false, gis_verified_at=null
           where id='${matchRow}'`,
      );
      const back = sql(`select address_line, gis_parcel_id from premises where id='${matchRow}'`);
      console.log(`  >> borrowed premises RESTORED: ${back}`);
      if (back !== `${savedAddress}|`) {
        console.log(`  FAIL  the borrowed premises was NOT put back (wanted "${savedAddress}|")`);
        fails++;
      }
    }
    if (borrowed) {
      sql(
        `update integration_connection set config = jsonb_set(config,'{base_url}',to_jsonb('${savedBaseUrl}'::text))
           where provider_key='gis_esri'`,
      );
      const restored = sql(
        `select config->>'base_url' from integration_connection where provider_key='gis_esri'`,
      );
      console.log(`\n  >> connector base_url RESTORED: ${restored}`);
      if (restored !== savedBaseUrl) {
        console.log(`  FAIL  the borrowed connector was NOT put back (${savedBaseUrl})`);
        fails++;
      }
    }
  }

  console.log(`\n${fails === 0 ? "ALL CHECKS PASSED" : fails + " CHECK(S) FAILED"}`);
  console.log("⚠ AND NONE OF THEM IS EVIDENCE ABOUT ANN ARBOR'S DATA — the layer read here is "
    + "apps/integrations/gis_esri_fixtures.py, constructed by hand and never recorded from the City.");
  console.log(`screenshots: ${OUT}`);
  process.exit(fails === 0 ? 0 : 1);
})();
