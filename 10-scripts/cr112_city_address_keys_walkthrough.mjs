/**
 * ── Trace ──────────────────────────────────────────────
 * Change:  CR-112 (2.290.0, commit 1c658337) — the City of Ann Arbor's ArcGIS
 *          address register becomes the source of addresses.
 * Screens: S16 the premises create wizard, step *Details* → the FIND THE
 *          ADDRESS panel (`features/metering/FindTheAddress.tsx`, mounted by
 *          `AddPremisesWizard.tsx`, routed at `/:tenant/premises/new`) ·
 *          S142 the connector view (`/:tenant/settings/integrations/gis_esri`)
 * Rules:   CLAUDE.md hard rule 8 (an address lives on `premises` and nowhere
 *          else) · hard-won law 2 (built is not wired) · law 6 (no gate in
 *          this repo reads rendered output) · law 7 (a check must tell pass
 *          from fail to a READER, and must declare what it SKIPPED beside
 *          what it checked) · BR-INT-022/024 (the breaker) · BR-INT-048
 *          (`C15`/`C16`) · BR-INT-075 (our ranking, grouped, capped) ·
 *          BR-MET-1173 (the parcel has its own column) · OQ-INT-1471 ruled
 *          2026-09-04 (b) *"type it, marked unchecked"*
 * Defects: this run found, and these are what its FAILing lines mean —
 *          DEF-INT-5599 an unreachable City is a 500, the breaker never counts
 *          it, and the panel vanishes as the clerk types · DEF-INT-5600 the
 *          City's address-POINT id never reaches the form, so units.gis_point_id
 *          is never written · DEF-INT-5601 CR-112's four new backend modules
 *          have no caller outside their own tests · DEF-INT-5602
 *          premises.gis_status is always NULL · DEF-INT-5603 the list is
 *          truncated at eight and nothing says so · DEF-MET-5604 the
 *          'Found on the city map' panel draws a green tick over nothing and
 *          its 'Change these' editor writes three fields the server discards.
 *          A FAIL here is one of those five until somebody shows otherwise;
 *          a PASS turning into a FAIL is new and is yours.
 * ───────────────────────────────────────────────────────
 *
 * ⚠⚠ **THIS WALK PROVES OUR CODE. IT PROVES NOTHING ABOUT THE CITY'S DATA.**
 * The egress proxy in this environment REFUSES `a2mapseg.a2gov.org` — a plain
 * `curl` to the FeatureServer returns code `000`, and inside Django the same
 * refusal arrives as `OSError: Tunnel connection failed: 403 Forbidden`. Not
 * one byte of Ann Arbor's register has ever been read here. Wherever this
 * script shows candidates it is showing a LOCAL STUB THIS FILE STARTS, shaped
 * by hand from what `adapters/gis_city.py::candidate_from` parses. A green run
 * means our search, our rendering and our columns behave; it does NOT mean the
 * Ann Arbor integration works.
 *
 * RUN IT:
 *     # 1 · a backend on the tip, against the shared demo database
 *     cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \
 *       DATABASE_URL="postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub" \
 *       JOBS_EAGER=false python3 manage.py runserver 127.0.0.1:8733 --noreload
 *     # 2 · the built SPA + an /api proxy
 *     (cd 07-frontend && ./node_modules/.bin/vite build)
 *     DIST=$PWD/07-frontend/dist BACKEND=http://127.0.0.1:8733 PORT=8751 \
 *       node <scratchpad>/walkserver.mjs
 *     # 3 · this walk
 *     BASE=http://127.0.0.1:8751 node 10-scripts/cr112_city_address_keys_walkthrough.mjs
 *
 * ⚠ **CHECK THE SERVED BUNDLE IS THE ONE YOU MEAN.** Step 0 prints it and the
 * backend behind it, because *which build am I looking at* is the question this
 * CR has got wrong twice. Two sibling lanes were serving other checkouts on
 * 8099/8411/8110 the day this was written.
 *
 * ⚠ **IT BORROWS THE TENANT'S CONNECTION FOR THE LENGTH OF THE RUN.** To make
 * candidates observable at all it repoints `integration_connection.config
 * ->base_url` for `gis_esri` at its own stub on 127.0.0.1, and puts the
 * original back in a `finally`. It prints the before and after and FAILS LOUDLY
 * if they differ. Set `CITY_STUB=0` to skip that entirely and walk only the
 * unreachable path.
 *
 * ── WHAT WOULD MAKE EACH STEP PASS WRONGLY (law 7, habit 2) ────────────────
 *  1 A REQUEST LEAVES — the panel fires a `q=` call on MOUNT, before anything
 *    is typed, and the app shell has its own global search box. A check that
 *    counted "an address-search request happened" or matched
 *    `input[type=search]` would pass without the clerk's text ever leaving.
 *    So: the request must carry the TYPED string in `q`, and the field is
 *    addressed as `#city-address-search` and never by role.
 *  2 A CANDIDATE COMES BACK — reading the fixture this file wrote instead of
 *    the server's answer would pass on an unwired backend. So the assertion
 *    reads the RESPONSE BODY off the wire and prints it verbatim, and step 0
 *    records whether the stub or the real City was behind it.
 *  3 BOTH KEYS ARE STORED — the screen shows the parcel the moment it is
 *    picked, from browser state, so a rendered parcel proves nothing about a
 *    column. And the create response is the server's own claim. So this step
 *    reads `premises.gis_parcel_id` and `units.gis_point_id` back out of
 *    PostgreSQL under `app.tenant_id`, after the wizard has finished.
 *  4 THE ADDRESS IS ON `premises` ONLY — a unit with a NULL city passes a
 *    value check whether or not the COLUMN exists. So this asks
 *    `information_schema` for an address column on `units`, which is the
 *    question hard rule 8 actually asks.
 *  5 FLAT OR GROUPED — `li` counted over the PAGE matches the nav, the
 *    stepper and the services chips. Every count here is scoped inside
 *    `[data-testid="find-the-address"]`, and "grouped" means a NESTED `ul`,
 *    not a heading that happens to look like one.
 *  6 NO RUN NOW — the word *run* appears on that screen in the nav item
 *    *Runbooks* and in every row of the run history. Matching `/run/i` over
 *    the body passes wrongly, in both directions. So this reads the page's
 *    own controls, with the app shell's nav excluded by name.
 *  7 THE THREE EMPTY-HANDED CASES — "the panel is gone" and "the panel says
 *    nothing found" both leave zero candidates on screen, so a candidate
 *    count cannot tell them apart. Each case is identified by the ELEMENT
 *    that means it: `[data-testid=no-matches]`, `[data-testid=city-offline]`,
 *    `[data-testid=city-unavailable]`, or the panel's absence.
 */
import { createRequire } from "node:module";
import { execFileSync } from "node:child_process";
import http from "node:http";
import { mkdirSync, existsSync, readdirSync } from "node:fs";
import { join } from "node:path";

const require = createRequire("file:///home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8751";
const T = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const TENANT_ID = process.env.TENANT_ID ?? "01a0a444-32e7-7df2-97c5-01865f274d41";
const PGURL = process.env.PGURL ?? "postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub";
const STUB_PORT = Number(process.env.STUB_PORT ?? 8760);
const USE_STUB = process.env.CITY_STUB !== "0";
const OUT = process.env.OUT ?? "/tmp/cr112-walk";
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
// AND `-tA` DOES NOT SUPPRESS IT. The first draft of this file took that whole
// string as the answer, and the line that restores the borrowed connector then
// wrote `SET\nhttps://…` back into `base_url`. It is dropped here, once, rather
// than at each call site.
const sql = (q) =>
  execFileSync("psql", [PGURL, "-tAc", `set app.tenant_id='${TENANT_ID}'; ${q}`], {
    encoding: "utf8",
  })
    .split("\n")
    .filter((line) => line.trim() !== "SET")
    .join("\n")
    .trim();

let fails = 0, skips = 0;
const say = (label, ok, detail = "") =>
  (console.log(`  ${ok ? "PASS" : "FAIL"}  ${label}${detail ? " — " + detail : ""}`), ok || fails++);
const skip = (label, why) => (console.log(`  SKIP  ${label} — ${why}`), skips++);

// ── the stub. NOT Ann Arbor. See the banner. ───────────────────────────────
//
// ⚠ **THE PARCEL KEYS CARRY A PER-RUN SUFFIX SO THIS WALK CAN BE RUN TWICE.**
// With fixed keys the second run is refused by `REFUSAL_PARCEL_TAKEN` — *"Another
// property already has that parcel."* — which is the product working correctly
// and the walk failing anyway, for a reason that reads like a broken store path.
// (That refusal was seen doing its job on the run that found this, so it is
// checked below rather than merely avoided.)
const RUN = Date.now().toString(36).slice(-5).toUpperCase();
// ⚠ **EVERY ROW NOW CARRIES A `point` AS WELL AS A `parcel`, AND THE RUN THAT
// FOUND `DEF-INT-5600` DID NOT (added 2026-09-17 by the lane that fixed it).**
// `PIN` is the parcel and `FULLPIN` is the City's ADDRESS-POINT key — the two
// keys `CR-112` exists to carry — and this stub offered only the first. So the
// step that reads `units.gis_point_id` back out of PostgreSQL could FAIL for
// two different reasons and could never PASS for any: our code dropped the key,
// AND the fixture never sent one. That is law 7's *incapable of passing* shape
// on a fixture instead of a check. With a point on every row the step has one
// meaning, which is the only thing that makes it evidence either way.
const ROWS = [
  { parcel: `09-09-29-${RUN}-001`, point: `09-09-29-${RUN}-001-0000`, address: "500 Main St",       city: "Ann Arbor", state: "MI", zip: "48104", lat: 42.279594, lng: -83.743841, score: 98, status: "ACTIVE" },
  { parcel: `09-09-29-${RUN}-002`, point: `09-09-29-${RUN}-002-0001`, address: "500 Main St Apt 1", city: "Ann Arbor", state: "MI", zip: "48104", lat: 42.279601, lng: -83.743850, score: 94, status: "ACTIVE" },
  { parcel: `09-09-29-${RUN}-003`, point: `09-09-29-${RUN}-003-0002`, address: "500 Main St Apt 2", city: "Ann Arbor", state: "MI", zip: "48104", lat: 42.279610, lng: -83.743860, score: 93, status: "ACTIVE" },
  { parcel: `09-09-29-${RUN}-004`, point: `09-09-29-${RUN}-004-0003`, address: "500 Main St Apt 3", city: "Ann Arbor", state: "MI", zip: "48104", lat: 42.279620, lng: -83.743870, score: 92, status: "RETIRED" },
  // ⚠ **TWELVE MORE SO THE CAP ACTUALLY BITES.** Without these the
  // truncation check passes on a four-row list and can never fail, which is
  // not a check. Twelve puts the stub's answer at sixteen, above
  // `adapters/gis_city.py::CANDIDATE_CAP` (8) and below `gis_search.py`'s
  // documented `BUILDING_CAP` (20) — so which cap the product ACTUALLY
  // enforces is a question this run answers rather than assumes.
  ...Array.from({ length: 12 }, (_, i) => ({
    parcel: `09-09-29-${RUN}-1${String(i).padStart(2, "0")}`,
    point: `09-09-29-${RUN}-1${String(i).padStart(2, "0")}-0${String(i).padStart(3, "0")}`,
    address: `500 Main St Unit ${100 + i}`, city: "Ann Arbor", state: "MI", zip: "48104",
    lat: 42.2797 + i / 10000, lng: -83.7439 - i / 10000, score: 90 - i, status: "ACTIVE",
  })),
];
let stubServer = null, savedBaseUrl = null, borrowed = false;
// ⚠ **THE STUB IS STARTED BEFORE THE CONNECTOR IS BORROWED, AND ITS `listen`
// IS AWAITED.** The first draft started it fire-and-forget and repointed
// `base_url` on the next line; a stale stub from an earlier run held the port,
// node raised an UNHANDLED `EADDRINUSE` error event, the process DIED, and the
// `finally` that puts the connector back never ran — leaving the tenant's live
// connector pointed at 127.0.0.1. Nothing else in this repo would have noticed.
function startStub() {
  return new Promise((resolve, reject) => {
    stubServer = http.createServer((req, res) => {
      const q = (new URL(req.url, "http://x").searchParams.get("q") || "").toLowerCase();
      const hit = q.includes("zzz") ? [] : ROWS.filter((r) => r.address.toLowerCase().includes(q.split(" ")[0]));
      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify({ candidates: hit }));
    });
    stubServer.once("error", reject);
    stubServer.listen(STUB_PORT, "127.0.0.1", resolve);
  });
}

try {
  // ── 0 · WHICH BUILD, WHICH BACKEND ──────────────────────────────────────
  console.log("\n0 · WHAT THIS RUN IS LOOKING AT");
  const html = await (await fetch(`${BASE}/`)).text();
  console.log(`  bundle served at ${BASE}: ${html.match(/assets\/(index-[\w-]+\.js)/)?.[1] ?? "(none found)"}`);
  console.log(`  database:            ${PGURL.replace(/\/\/[^@]*@/, "//***@")}`);
  console.log(`  tenant:              ${T} (${TENANT_ID})`);
  savedBaseUrl = sql(`select config->>'base_url' from integration_connection where provider_key='gis_esri';`);
  console.log(`  connector base_url:  ${savedBaseUrl || "(no gis_esri connection)"}`);
  if (USE_STUB) {
    await startStub();
    sql(`update integration_connection set config = jsonb_set(config::jsonb,'{base_url}','"http://127.0.0.1:${STUB_PORT}/query"') where provider_key='gis_esri';`);
    borrowed = true;
    console.log(`  >> BORROWED: base_url repointed at this file's LOCAL STUB on ${STUB_PORT}. NOT the City.`);
  } else {
    console.log("  >> CITY_STUB=0 — walking the live connector only; steps 2-5 will SKIP.");
  }

  const b = await chromium.launch({ executablePath: chrome(), args: ["--no-sandbox"] });
  const p = await b.newPage({ viewport: { width: 1440, height: 1800 } });
  const searches = [];   // every address-search that left, with its answer
  const writes = [];     // every non-GET to /api
  p.on("response", async (r) => {
    const u = r.url();
    if (!u.includes("/api/")) return;
    let body = ""; try { body = await r.text(); } catch { /* streamed */ }
    if (u.includes("address-search")) searches.push({ url: decodeURIComponent(u), status: r.status(), body });
    else if (r.request().method() !== "GET") writes.push({ url: u, status: r.status(), body, sent: r.request().postData() });
  });

  const signIn = async () => {
    await p.goto(`${BASE}/${T}/signin`, { waitUntil: "networkidle" });
    await p.fill("#signin-email", EMAIL);
    await p.fill("#signin-password", PASSWORD);
    await p.click('button[type="submit"]');
    await p.waitForTimeout(2500);
  };
  const toDetails = async () => {
    await p.goto(`${BASE}/${T}/premises/new`, { waitUntil: "networkidle" });
    await p.waitForTimeout(1500);
    await p.getByText("One premise", { exact: true }).first().click();
    await p.waitForTimeout(400);
    await p.getByRole("button", { name: /Continue/i }).first().click();
    await p.waitForTimeout(2000);
  };
  const PANEL = '[data-testid="find-the-address"]';

  await signIn();

  // ── 1 · DOES THE FORM CALL THE SEARCH AT ALL? ───────────────────────────
  console.log("\n1 · THE PREMISES CREATE FORM AND THE SEARCH");
  await toDetails();
  say("the FIND THE ADDRESS panel is mounted on step 2 of /premises/new",
      (await p.locator(PANEL).count()) === 1);
  say("it has its own address field, #city-address-search (NOT the shell's search box)",
      (await p.locator("#city-address-search").count()) === 1);
  const before = searches.length;
  await p.fill("#city-address-search", "500 Main");
  await p.waitForTimeout(3000);
  const typed = searches.slice(before).filter((s) => /[?&]q=[^&]+/.test(s.url) && !/[?&]q=(&|$)/.test(s.url));
  say("typing sends a request to OUR backend carrying the typed text",
      typed.length > 0, typed.length ? typed[typed.length - 1].url.split("/api/")[1] : "no q= request left");
  await p.screenshot({ path: `${OUT}/01-typed.png`, fullPage: true });

  // ── 2 · WHAT COMES BACK ─────────────────────────────────────────────────
  console.log("\n2 · WHAT A CANDIDATE ACTUALLY CARRIES");
  const answer = typed[typed.length - 1];
  if (!answer || answer.status !== 200) {
    say(`the search answers 200 (it answered ${answer ? answer.status : "nothing"})`, false,
        answer ? answer.body.slice(0, 160) : "");
    skip("what a candidate carries", "no 200 to read");
  } else {
    const parsed = JSON.parse(answer.body);
    const one = parsed.candidates?.[0];
    console.log(`  one candidate, verbatim off the wire:\n    ${JSON.stringify(one)}`);
    say("a candidate carries the City's PARCEL id", Boolean(one && one.parcel), one ? `parcel=${one.parcel}` : "");
    const pointKey = one && Object.keys(one).find((k) => /point/i.test(k));
    say("a candidate carries the City's address-POINT id", Boolean(pointKey),
        pointKey ? `key=${pointKey}` : `no point-ish key in [${one ? Object.keys(one).join(", ") : ""}]`);
    say("a candidate carries the City's own Status (ruling 10, stored as given)",
        Boolean(one && one.status !== undefined),
        one && one.status === undefined ? "no `status` key on the candidate" : "");
    const rendered = await p.locator(`${PANEL} li`).first().innerText();
    console.log(`  the same candidate as RENDERED:\n    ${JSON.stringify(rendered.replace(/\n/g, " | "))}`);
  }

  // ── 5 · FLAT OR GROUPED (scoped INSIDE the panel) ───────────────────────
  console.log("\n5 · FLAT LIST OR GROUPED BY BUILDING");
  const panel = p.locator(PANEL);
  const uls = await panel.locator("ul").count();
  const lis = await panel.locator("li").count();
  const nested = await panel.locator("ul ul").count();
  console.log(`  inside the panel only: ul=${uls}  li=${lis}  nested ul=${nested}`);
  say("the candidate list is GROUPED BY BUILDING (a nested list, per BR-INT-075)",
      nested > 0, nested === 0 ? `flat: ${lis} sibling rows under ${uls} list` : "");
  const offered = JSON.parse(answer && answer.status === 200 ? answer.body : '{"candidates":[]}').candidates.length;
  console.log(`  the stub offered ${ROWS.length} rows; the server passed on ${offered}; the screen drew ${lis}`);
  say("a TRUNCATED list says so, so the clerk knows a row may be missing",
      (await panel.getByText(/Keep typing to narrow/i).count()) > 0,
      offered < ROWS.length
        ? `${ROWS.length - offered} rows were dropped silently (cap applied: ${offered}, documented cap: 20)`
        : "nothing was truncated on this run");
  say("the ranking is labelled as OURS (`integrations.gis.our_ranking`)",
      (await panel.getByText(/Ordered by us/i).count()) > 0,
      "no 'Ordered by us, not the city.' anywhere in the panel");
  await panel.screenshot({ path: `${OUT}/02-candidate-list.png` });

  // ── 3+4 · PICK ONE, SAVE, THEN READ THE COLUMNS ─────────────────────────
  console.log("\n3 · PICKING ONE AND WHAT REACHES THE DATABASE");
  let made = null;
  if (!answer || answer.status !== 200) {
    skip("the store path", "no candidate to pick");
    skip("hard rule 8 on the written row", "nothing was written");
  } else {
    await panel.locator("li").first().getByRole("button", { name: /Use this/i }).click();
    await p.waitForTimeout(1200);
    await p.screenshot({ path: `${OUT}/03-after-pick.png`, fullPage: true });
    // ⚠ **THE ADDRESS FIELD IS LEFT EXACTLY AS THE PICK FILLED IT.** The first
    // draft typed a unique marker into `#address_line` so the row could be
    // found again, and the wizard treated that edit as the clerk overriding the
    // City's answer: nothing was written and five checks failed on an empty
    // result set, which reads like a broken store path rather than a broken
    // walk. The row is identified from the create RESPONSE instead, which is
    // also the only identifier a clerk would ever see.
    await p.selectOption("#premises_type", { index: 1 }).catch(() => {});
    await p.selectOption("#unit_type", { index: 1 }).catch(() => {});
    await p.getByRole("button", { name: /^Continue$/i }).first().click();
    await p.waitForTimeout(1800);
    await p.getByRole("button", { name: /Save|Create/i }).last().click();
    await p.waitForTimeout(4000);
    await p.screenshot({ path: `${OUT}/04-saved.png`, fullPage: true });

    const created = writes.filter((w) => /premises/.test(w.url) && w.status === 201).pop();
    try { made = created ? JSON.parse(created.body) : null; } catch { /* not json */ }
    say("the wizard's Create reached the server and was accepted (201)", Boolean(made),
        created ? `${created.status} ${created.url.split("/api/")[1]}` : "no 201 to a premises route");
    if (!made) skip("the stored columns", "nothing was created to read back");
    else {
    console.log(`  created ${made.premise_no}; the SERVER's own claim: gis_parcel_id=${JSON.stringify(made.gis_parcel_id)} gis_status=${JSON.stringify(made.gis_status)}`);
    const row = sql(`select coalesce(premise_no,'')||'|'||coalesce(gis_parcel_id,'')||'|'||coalesce(gis_status,'')||'|'||gis_unchecked::text from premises where premise_no='${made.premise_no}';`);
    const [pno, parcelCol, statusCol, unchecked] = (row || "|||").split("|");
    say("the premises row is in the database, read back under app.tenant_id", Boolean(pno), `premise ${pno || "(none)"}`);
    say("premises.gis_parcel_id holds the City's parcel key", Boolean(parcelCol),
        `gis_parcel_id=${JSON.stringify(parcelCol)}`);
    say("premises.gis_status holds the City's own Status (ruling 10)", Boolean(statusCol),
        `gis_status=${JSON.stringify(statusCol)} — the stub sent status="ACTIVE"`);
    // ⚠ `::text` on a PostgreSQL boolean renders `true`/`false`, NOT `t`/`f` —
    // `t`/`f` is psql's DISPLAY of a bare boolean column. The first draft tested
    // for "f" and reported a correct row as a failure, which is this repo's
    // law 7 in miniature: the check was wrong, not the code.
    say("a premises created FROM the City is not marked unchecked",
        unchecked === "false" || unchecked === "f", `gis_unchecked=${unchecked}`);
    const pointCol = sql(`select coalesce(u.gis_point_id,'') from units u join premises p on p.id=u.premises_id where p.premise_no='${made.premise_no}' limit 1;`);
    say("units.gis_point_id holds the City's address-point key", Boolean(pointCol),
        `gis_point_id=${JSON.stringify(pointCol)}`);

    }

    console.log("\n4 · HARD RULE 8 — THE ADDRESS IS ON `premises` AND NOWHERE ELSE");
    const unitAddrCols = sql(`select coalesce(string_agg(column_name,','),'') from information_schema.columns where table_name='units' and column_name in ('address_line','address','city','state','postal_code','zip');`);
    say("`units` declares NO address column of its own", unitAddrCols === "",
        unitAddrCols ? `units carries ${unitAddrCols}` : "checked address_line/address/city/state/postal_code/zip");
    if (made) {
      const premAddr = sql(`select coalesce(address_line,'')||' / '||coalesce(city,'')||' / '||coalesce(state,'') from premises where premise_no='${made.premise_no}';`);
      say("the address landed on the premises row itself", premAddr.trim().length > 3, premAddr);
    } else skip("the address on the written row", "nothing was created");
  }

  // ── 6 · IS THERE A RUN NOW CONTROL? ─────────────────────────────────────
  // the same parcel twice — `DEF-INT-4273`'s refusal, now a product rule rather
  // than a caught constraint (`BR-MET-1173`: `gis_parcel_id` has no unique index).
  if (made) {
    await toDetails();
    await p.fill("#city-address-search", "500 Main");
    await p.waitForTimeout(3000);
    await p.locator(`${PANEL} li`).first().getByRole("button", { name: /Use this/i }).click();
    await p.waitForTimeout(1000);
    await p.selectOption("#premises_type", { index: 1 }).catch(() => {});
    await p.getByRole("button", { name: /^Continue$/i }).first().click();
    await p.waitForTimeout(1800);
    await p.getByRole("button", { name: /Save|Create/i }).last().click();
    await p.waitForTimeout(3500);
    await p.screenshot({ path: `${OUT}/04b-parcel-taken.png`, fullPage: true });
    const refusal = await p.getByText(/already has that parcel/i).count();
    say("picking a parcel another property already holds is refused in words",
        refusal > 0, refusal ? "\"Another property already has that parcel.\"" : "the second create was allowed through");
  } else skip("the parcel-already-taken refusal", "no first create to collide with");

  // ── 3b · THE PANEL THAT READS BACK WHAT THE LOOKUP FOUND ───────────────
  // False pass: the panel is drawn for EVERY property, so finding it proves
  // nothing. What is asked here is whether its heading is true when nothing
  // has been found, and whether its editor's values survive a save.
  console.log("\n3b · THE `Found on the city map` PANEL, WITH NOTHING FOUND");
  await toDetails();
  const found = p.locator('[data-testid="found-on-the-city-map"]');
  const drawn = (await found.count()) === 1;
  const text = drawn ? (await found.innerText()).replace(/\n+/g, " | ") : "";
  console.log(`  with no lookup run at all, the panel says: ${JSON.stringify(text)}`);
  say("the panel does not claim `Found on the city map` before anything is found",
      !drawn || !/found on the city map/i.test(text),
      drawn ? "a green tick and the word Found, above three `not yet` rows" : "");
  if (drawn) {
    await p.getByRole("button", { name: /Change these/i }).click();
    await p.waitForTimeout(600);
    const ed = p.locator('[data-testid="city-map-editor"]');
    const ids = [];
    for (const c of await ed.locator("input").all()) ids.push(await c.getAttribute("id"));
    console.log(`  its editor offers: ${ids.map((i) => `#${i}`).join(", ")}`);
    say("the parcel box is bound to `gis_parcel_id`, the column CR-112 gave it",
        ids.includes("gis_parcel_id"),
        ids.includes("external_ref") ? "still bound to `external_ref`, which BR-MET-1173 retired as the parcel's home" : "");
    const HAND = `HANDTYPED-${RUN}`;
    await ed.locator("input").first().fill(HAND);
    await p.fill("#address_line", `9 Handtyped Way ${RUN}`);
    await p.selectOption("#premises_type", { index: 1 }).catch(() => {});
    await p.getByRole("button", { name: /^Continue$/i }).first().click();
    await p.waitForTimeout(1800);
    await p.getByRole("button", { name: /Save|Create/i }).last().click();
    await p.waitForTimeout(4000);
    await p.screenshot({ path: `${OUT}/04c-hand-typed.png`, fullPage: true });
    const kept = sql(`select coalesce(external_ref,'')||'|'||coalesce(gis_parcel_id,'') from premises where address_line like '%9 Handtyped Way ${RUN}%';`);
    say("a parcel typed by hand into that editor is STORED (or the save is refused)",
        kept.replace("|", "").length > 0,
        `the save returned success and the row holds external_ref|gis_parcel_id = ${JSON.stringify(kept)}`);
  }

  console.log("\n6 · A RUN NOW CONTROL ON THE CONNECTOR SCREEN");
  await p.goto(`${BASE}/${T}/settings/integrations/gis_esri`, { waitUntil: "networkidle" });
  await p.waitForTimeout(2000);
  await p.screenshot({ path: `${OUT}/05-connector.png`, fullPage: true });
  // Scoped: the page's own controls, with the app shell's nav excluded by name.
  const NAV = new Set(["Dashboard","Plans & Rates","Premises","Assets","Accounts","Reads","Billing",
    "Payments","Work","Finance","Runbooks","Reports","Settings"]);
  const controls = [...await p.getByRole("button").allInnerTexts(), ...await p.getByRole("link").allInnerTexts()]
    .map((s) => s.trim().replace(/\s+/g, " ")).filter(Boolean).filter((s) => !NAV.has(s));
  console.log(`  the connector screen's own controls: ${controls.map((c) => `"${c}"`).join(", ")}`);
  const runControl = controls.find((c) => /^run\b|run now|run it/i.test(c));
  say("the connector screen offers a way to RUN the reconciliation", Boolean(runControl),
      runControl ? runControl : "no control whose label starts with Run (Runbooks is the shell's nav item)");

  // ── 7 · THE THREE EMPTY-HANDED CASES ────────────────────────────────────
  console.log("\n7 · NOTHING FOUND · THE CITY UNREACHABLE · NO CONNECTOR AT ALL");
  if (USE_STUB) {
    await toDetails();
    await p.fill("#city-address-search", "zzz nowhere");
    await p.waitForTimeout(3000);
    await p.screenshot({ path: `${OUT}/06-nothing-found.png`, fullPage: true });
    const stillThere = (await p.locator(PANEL).count()) === 1;
    const noMatch = (await p.locator('[data-testid="no-matches"]').count()) === 1;
    say("an EMPTY result keeps the panel and says so plainly", stillThere && noMatch,
        stillThere ? (noMatch ? await p.locator('[data-testid="no-matches"]').innerText() : "panel stayed but said nothing") : "the panel vanished");
    say("the clerk can still type the address by hand afterwards",
        (await p.locator("#address_line").count()) === 1);
  } else skip("the empty-result case", "needs CITY_STUB=1");

  // ── THE CITY UNREACHABLE ────────────────────────────────────────────────
  //
  // ⚠ **THIS STEP USED TO RESTORE THE SEEDED `base_url` AND CALL THAT
  // *unreachable*. ON A SEEDED DEMO TENANT IT IS THE OPPOSITE (corrected
  // 2026-09-17, the lane that fixed `DEF-INT-5599`).** `seed_gis_city` points
  // `gis_esri` at `https://gis.brazosbend.example/addr`, and
  // `apps/integrations/gis_fixtures.py::transport_for` INTERCEPTS every host
  // ending `.example` and answers it from a RECORDING in 300 ms. So the
  // reserved name is the one host in the world that can never fail to connect
  // here, and this step measured a healthy fixture while reporting on an
  // unreachable City. It happened to be right on the shared checkout only
  // because THAT tenant's connector pointed at Ann Arbor for real.
  //
  // **A step whose subject depends on what somebody seeded is not a step.** So
  // the address is now stated here: the City of Ann Arbor's own service, which
  // this environment's egress proxy refuses with
  // `OSError: Tunnel connection failed: 403 Forbidden` — a socket that never
  // opens, which is exactly what `DEF-INT-5599` is about and is NOT a timeout.
  // `savedBaseUrl` is still what the `finally` puts back.
  const UNREACHABLE =
    "https://a2mapseg.a2gov.org/a2arcgis/rest/services/SEU/SEUQualifiedAddress/FeatureServer/0/query";
  sql(`update integration_connection set config = jsonb_set(config::jsonb,'{base_url}','"${UNREACHABLE}"') where provider_key='gis_esri';`);
  // The breaker is cleared first, so `consecutive_timeouts` after this step is
  // what THIS step counted and not what an earlier run left behind.
  sql(`update integration_connection set config = config - 'breaker' where provider_key='gis_esri';`);
  borrowed = true;
  console.log(`  >> POINTED AT AN UNREACHABLE HOST: ${UNREACHABLE}`);
  console.log("     (not a stub and not a fixture — this host is refused by the egress proxy)");
  await toDetails();
  await p.fill("#city-address-search", "500 Main");
  await p.waitForTimeout(6000);
  await p.screenshot({ path: `${OUT}/07-city-unreachable.png`, fullPage: true });
  const last = searches[searches.length - 1];
  console.log(`  the live City answered: ${last ? `${last.status} ${last.body.slice(0, 140)}` : "(nothing)"}`);
  say("an unreachable City is answered as a REFUSAL, not a 500",
      Boolean(last) && last.status !== 500, last ? `status ${last.status}` : "");
  const amber = await p.locator('[data-testid="city-offline"]').count();
  const grey = await p.locator('[data-testid="city-unavailable"]').count();
  const gone = (await p.locator(PANEL).count()) === 0;
  say("frame 66.2's amber `The City is not answering` box is shown", amber === 1,
      gone ? "the whole panel vanished, taking the clerk's typed text with it" : `city-offline=${amber} city-unavailable=${grey}`);
  say("the clerk can still type the address by hand (OQ-INT-1471 (b))",
      (await p.locator("#address_line").count()) === 1);
  const brk = sql(`select coalesce(config->'breaker'->>'consecutive_timeouts','-') from integration_connection where provider_key='gis_esri';`);
  say("BR-INT-022's breaker counted the failure", brk !== "0" && brk !== "-",
      `consecutive_timeouts=${brk} after a failing search`);

  // no connector at all — interception, so nothing shared is touched.
  await p.route("**/integrations/gis_esri/address-search**", (route) =>
    route.fulfill({ status: 409, contentType: "application/json",
      body: JSON.stringify({ code: "CONFLICT", message_key: "integrations.gis.not_connected", params: {}, field_errors: [], br_ref: "BR-INT-001" }) }));
  await toDetails();
  await p.waitForTimeout(2500);
  await p.screenshot({ path: `${OUT}/08-not-connected.png`, fullPage: true });
  say("a tenant with NO City connector is told once, quietly, and the form still works",
      (await p.locator('[data-testid="city-unavailable"]').count()) === 1 &&
      (await p.locator("#address_line").count()) === 1,
      await p.locator('[data-testid="city-unavailable"]').innerText().catch(() => "no city-unavailable line"));

  await b.close();
} finally {
  if (savedBaseUrl && (borrowed || USE_STUB)) {
    sql(`update integration_connection set config = jsonb_set(config::jsonb,'{base_url}','"${savedBaseUrl}"') where provider_key='gis_esri';`);
    const now = sql(`select config->>'base_url' from integration_connection where provider_key='gis_esri';`);
    console.log(`\n  connector base_url on the way out: ${now}`);
    if (now !== savedBaseUrl) { console.log("  !! NOT RESTORED — put it back by hand before you leave."); fails++; }
  }
  if (stubServer) stubServer.close();
}

console.log(`\n${fails === 0 ? "ALL CHECKS PASSED" : `${fails} CHECK(S) FAILED`}${skips ? `, ${skips} skipped` : ""}.`);
console.log(`screenshots: ${OUT}`);
console.log("⚠ green here means OUR code behaves. The City's own server was never reached.");
process.exit(fails === 0 ? 0 : 1);
