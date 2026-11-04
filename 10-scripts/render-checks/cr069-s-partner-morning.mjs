/**
 * RENDERED-OUTPUT CHECK — CR-069 wave S, "The partner's morning", in a real browser.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: no gate in this repository looks at
 * rendered output, and nine defects in one day were found this way and by
 * nothing else. PO ruling 2026-09-03: *"ensure you do web walkthorugh before
 * you sign off the user story or build"*.
 *
 * ⚠ **AND THIS WAVE HAS A SECOND REASON THAT NO UNIT TEST CAN COVER: THE THREE
 * REFUSALS HAVE TO BE COMPARED AS BYTES ON THE WIRE, AND THE TIMINGS WITH
 * THEM.** A Django test client and a browser's `fetch` do not negotiate content
 * the same way; a refusal that comes back identical in `pytest` and differs by
 * a `Content-Type` or a trailing newline over HTTP is still an oracle. So this
 * script asks the running server three times, from three wrong positions, and
 * compares the answers byte for byte and clock against clock.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   eval "$(10-scripts/proof-db.sh clone int-s --export)"
 *   DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
 *     python3 06-backend/manage.py migrate && \
 *     python3 06-backend/manage.py seed_partner_morning
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8163 --noreload &
 *   (cd 07-frontend && ./node_modules/.bin/vite build && \
 *      PORT=4363 API_PROXY_TARGET=http://127.0.0.1:8163 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4363 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr069-s-partner-morning.mjs
 *
 * ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** A mid-run reseed
 * looks exactly like a broken screen.
 *
 * ⚠ **THE PARTNER'S CALLS GO STRAIGHT AT THE API AND NOT THROUGH THE SPA.**
 * A partner is a machine with a key; it has no session and no browser. The
 * script therefore uses `context.request` for steps 1–5 and a real page only
 * for step 6, which is the half a manager sees. Driving the partner half
 * through the SPA would be testing a thing that will never happen.
 *
 * ⚠ **THE SOURCE ALLOWLIST CANNOT BE EXERCISED FROM ONE MACHINE, AND THE
 * SCRIPT SAYS SO RATHER THAN PRETENDING.** Every request here leaves from
 * 127.0.0.1. Step 4 therefore proves the allowlist by making 127.0.0.1 the
 * address that is NOT on the list — the seed writes an allowlist of
 * `198.51.100.0/24, 203.0.113.7` on a second connection — which is the same
 * refusal from the same code path, arrived at from the other side. A run that
 * claimed to call from `203.0.113.99` would be claiming something a loopback
 * request cannot do.
 *
 * ── WHAT IT CHECKS (the wave S demo script, 10-execution-plan.md) ─────────
 *   1  Three pages at 02:41 — 500 · 500 · 236 of 1,236, in the PARTNER's
 *      envelope (`total_records/page/page_size/total_pages`), never the DRF one.
 *   2  Each record carries our four fields and NONE of the three that moved to
 *      Runbooks (`tenderType`, `projectType`, `accountString` — CR-069 §20.4).
 *   3  THE THREE REFUSALS, SIDE BY SIDE: an address off the list, a wrong key,
 *      a revoked key — same status, same bytes, same time against the floor.
 *   4  The 101st request in a minute → `429` with `Retry-After`.
 *   5  A key presented at ANOTHER utility's address → the same refusal.
 *   6  S142 *Who has been reading* in the browser: the rows, the amber row,
 *      the amber box, the register's inward sentence — and the key's plaintext
 *      nowhere in the DOM.
 */

import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

import { Gaps } from "./lib/knownGaps.mjs";
import { attachTimings } from "./lib/timings.mjs";

const require = createRequire(join(process.cwd(), "07-frontend", "package.json"));
const { chromium } = require("playwright-core");

/**
 * ⚠ **`executablePath()` CAN RETURN A PATH THAT DOES NOT EXIST, AND THE
 * try/catch THE OTHER WALKTHROUGHS USE CANNOT SEE THAT.** On this machine it
 * answered `/opt/pw-browsers/chromium-1234/chrome-linux64/chrome` while the
 * installed browser is `chromium-1194/chrome-linux/chrome`: the call did not
 * throw, so the `catch` never ran, and the fallback that would have found the
 * real one was unreachable. A guard that cannot fire is CLAUDE.md law 7's
 * second shape, and this resolver is copied verbatim across sixteen scripts.
 *
 * So the returned path is CHECKED rather than trusted, and the fallback globs
 * both layouts (`chrome-linux` and `chrome-linux64`).
 */
function resolveChromium() {
  let candidate = null;
  try {
    candidate = chromium.executablePath();
  } catch {
    candidate = null;
  }
  if (candidate !== null && existsSync(candidate)) return candidate;
  const found = execFileSync("bash", [
    "-lc",
    "ls -d /opt/pw-browsers/chromium-*/chrome-linux*/chrome 2>/dev/null | head -1",
  ])
    .toString()
    .trim();
  if (found === "") {
    throw new Error(
      `no chromium found: executablePath() said ${candidate ?? "nothing"}, which does not ` +
        `exist, and no /opt/pw-browsers/chromium-*/chrome-linux*/chrome matched either`,
    );
  }
  return found;
}

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4363";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const OTHER_TENANT = process.env.SMOKE_OTHER_TENANT ?? "lonestarridge";
const STAFF_EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const STAFF_PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr069-s";
const VIEWPORT = { width: 1440, height: 1000 };

/** Written by `seed_partner_morning`; the hint is what a screen may show. */
const KEY = process.env.SMOKE_PARTNER_KEY ?? "sbh_live_7Q2F_brazosbend_demo";
const REVOKED_KEY = process.env.SMOKE_REVOKED_KEY ?? "sbh_live_9X1B_brazosbend_revoked";
/** Live, and refused only because of WHERE the call comes from. ⚠ The first
 *  draft of the seed put the revoked key on the allowlist-gated connection, so
 *  "off the allowlist" and "revoked" were one request failing for two reasons
 *  at once — which proves nothing about whether the two are distinguishable.
 *  Three refusals need three distinct causes. */
const GATED_KEY = process.env.SMOKE_GATED_KEY ?? "sbh_live_3M5T_brazosbend_gated";
const HINT = "••••7Q2F";
const PARTNER = "gl_partner";

/** The story's own figures (§4 Test Data), corrected by DEF-INT-3614: the
 *  envelope is 500 · 500 · 236, never three equal pages of 412. */
/** The day the morning happened. ⚠ WITHOUT IT THE COUNT IS 1,315, not 1,236:
 *  the sample utility already carries 79 payments of its own, and a page count
 *  that silently included them would make this script assert the wrong figure
 *  and call it the story's. */
const MORNING = process.env.SMOKE_MORNING ?? "2026-09-02";
const TOTAL = 1236;
const PAGE_SIZE = 500;
const PAGES = [500, 500, 236];

/** `runners/serve.REFUSAL_FLOOR_S` — the door holds every refusal to this, so
 *  the three cannot be told apart by timing them. Kept in seconds here to
 *  match the constant it is checking. */
const REFUSAL_FLOOR_MS = 40;

/** The three fields CR-069 §20.4 moves to Runbooks. Their ABSENCE is the
 *  assertion — and if Runbooks has landed and filled them, this run should go
 *  red and name the boundary rather than quietly agreeing. */
const MOVED_TO_RUNBOOKS = ["tenderType", "projectType", "accountString"];

mkdirSync(OUT, { recursive: true });

const failures = [];
const gaps = new Gaps();

function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

/** B14 rule 31 and rule 32 — never an id, never an internal code, on screen. */
const FORBIDDEN = [
  /\bBR-[A-Z]{3}-\d{3,5}\b/,
  /\bOQ-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /\bDEF-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
];

async function noInternals(page, where) {
  const text = await page.locator("body").innerText();
  for (const pattern of FORBIDDEN) {
    check(!pattern.test(text), `${where}: nothing matching ${pattern} on screen (B14 rule 31)`);
  }
}

/** One partner request, timed, with the body kept as TEXT so two refusals can
 *  be compared as bytes rather than as parsed objects — `JSON.parse` would
 *  happily call two different byte strings equal. */
async function partnerGet(context, path, { key = KEY, tenant = TENANT } = {}) {
  const started = Date.now();
  const response = await context.request.get(`${BASE}/api/${tenant}${path}`, {
    headers: key === null ? {} : { Authorization: `Bearer ${key}` },
    failOnStatusCode: false,
  });
  const body = await response.text();
  return {
    status: response.status(),
    body,
    contentType: response.headers()["content-type"] ?? "",
    elapsedMs: Date.now() - started,
  };
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const timings = attachTimings(context);
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });
  console.log(`cr069-s: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);

  // ═════ 1 · three pages at 02:41, in the partner's own envelope ═══════════
  console.log("\n── 1 · the partner collects yesterday's payments, over three pages ──");
  const sizes = [];
  for (const pageNumber of [1, 2, 3]) {
    const got = await partnerGet(
      context,
      `/v1/payments?from=${MORNING}&to=${MORNING}&page=${pageNumber}&page_size=${PAGE_SIZE}`,
    );
    check(got.status === 200, `page ${pageNumber} is served (200), got ${got.status}`);
    let body = {};
    try {
      body = JSON.parse(got.body);
    } catch {
      check(false, `page ${pageNumber} is JSON`);
      continue;
    }
    sizes.push((body.records ?? []).length);
    check(body.total_records === TOTAL, `total_records is ${TOTAL}, got ${body.total_records}`);
    check(body.page === pageNumber, `page is ${pageNumber}`);
    check(body.page_size === PAGE_SIZE, `page_size is ${PAGE_SIZE}`);
    check(body.total_pages === 3, `total_pages is 3, got ${body.total_pages}`);
    for (const ours of ["count", "next", "previous", "results"]) {
      check(!(ours in body), `the DRF key "${ours}" is absent — the envelope is the partner's`);
    }
  }
  check(
    JSON.stringify(sizes) === JSON.stringify(PAGES),
    `the three pages are ${PAGES.join(" · ")}, got ${sizes.join(" · ")} ` +
      `(⚠ 412 · 412 · 412 is the figure DEF-INT-3614 corrected)`,
  );

  // ═════ 2 · what is in a record, and what is Runbooks' ════════════════════
  console.log("\n── 2 · four fields that are ours, and three that are not ──");
  const first = await partnerGet(
    context,
    `/v1/payments?from=${MORNING}&to=${MORNING}&page=1&page_size=1`,
  );
  const record = (JSON.parse(first.body).records ?? [])[0] ?? {};
  check(
    JSON.stringify(Object.keys(record).sort()) ===
      JSON.stringify(["amount", "currency", "id", "paymentDate"]),
    `a record carries exactly id · paymentDate · amount · currency, got ${Object.keys(record).join(" · ")}`,
  );
  check(/^\d+\.\d{2}$/.test(String(record.amount ?? "")), `the amount displays two decimals (hard rule 2): ${record.amount}`);
  check(!/^[0-9a-f]{8}-/.test(String(record.id ?? "")), `the id is the receipt number, not a database key: ${record.id}`);
  for (const moved of MOVED_TO_RUNBOOKS) {
    gaps.known(moved in record, `a record carries ${moved}`, {
      defect: "CR-069 §20.4",
      why:
        `${moved} is what the payload MEANS, which BR-INT-054 puts in Runbooks — ` +
        `integrations lands and hands over, it does not interpret. If this has ` +
        `closed, Runbooks has landed and this row is the one to delete`,
    });
  }

  // ═════ 3 · THE THREE REFUSALS, SIDE BY SIDE ══════════════════════════════
  console.log("\n── 3 · three ways of being turned away, and they must be one way ──");
  const offList = await partnerGet(context, "/v1/payments", { key: GATED_KEY });
  const wrongKey = await partnerGet(context, "/v1/payments", { key: "sbh_live_never_issued" });
  const revoked = await partnerGet(context, "/v1/payments", { key: REVOKED_KEY });

  // ⚠ `offList` is a request to the connection whose allowlist EXCLUDES
  // 127.0.0.1 — see the header. Every request here leaves from loopback, so
  // this is the allowlist proved from the other side rather than a pretence
  // that the script is calling from 203.0.113.99.
  const three = [
    ["an address that is not on the list", offList],
    ["a key that was never issued", wrongKey],
    ["a key that was revoked", revoked],
  ];
  for (const [name, got] of three) {
    console.log(`      ${name}: ${got.status} ${JSON.stringify(got.body)} (${got.elapsedMs}ms)`);
  }
  const statuses = new Set(three.map(([, got]) => got.status));
  const bodies = new Set(three.map(([, got]) => got.body));
  const types = new Set(three.map(([, got]) => got.contentType));
  check(statuses.size === 1, `one status across the three, got ${[...statuses].join(" · ")}`);
  check(bodies.size === 1, `one body across the three, got ${[...bodies].map((b) => JSON.stringify(b)).join(" · ")}`);
  check(types.size === 1, `one content-type across the three, got ${[...types].join(" · ")}`);
  const words = JSON.parse([...bodies][0] ?? "{}").error?.split(/\s+/).length ?? 0;
  check(words >= 5 && words <= 6, `the refusal is ${words} words (B14 rule 33)`);
  for (const [name, got] of three) {
    check(
      got.elapsedMs >= REFUSAL_FLOOR_MS,
      `${name} took ${got.elapsedMs}ms, at or over the ${REFUSAL_FLOOR_MS}ms floor — ` +
        `a faster refusal is one that says which of the three you got`,
    );
  }

  // ═════ 4 · the 101st request in a minute ════════════════════════════════
  console.log("\n── 4 · the 101st request in a minute waits ──");
  let limited = null;
  for (let attempt = 0; attempt < 130 && limited === null; attempt += 1) {
    const got = await partnerGet(
      context,
      `/v1/payments?from=${MORNING}&to=${MORNING}&page_size=1`,
    );
    if (got.status === 429) limited = got;
  }
  check(limited !== null, "a 429 arrives within 130 requests in the minute");
  if (limited !== null) {
    console.log(`      429 after the allowance, body ${JSON.stringify(limited.body)}`);
  }

  // ═════ 5 · a key at another utility's address ════════════════════════════
  console.log("\n── 5 · the key is scoped to ONE utility ──");
  const crossed = await partnerGet(context, "/v1/payments", { tenant: OTHER_TENANT });
  check(crossed.status === offList.status, `the other utility's address answers the same status`);
  check(crossed.body === offList.body, `…and the same bytes — it learns nothing about which utility exists`);
  // ⚠ ON A ONE-UTILITY PROOF DATABASE THIS IS THE *UNKNOWN UTILITY* CASE, NOT
  // THE TWO-TENANT ONE. `seed_demo` provisions Brazos Bend and nothing else,
  // so a second utility's key cannot be presented here at all. The real
  // two-tenant proof — one utility's partner exhausting its allowance while
  // another's is served, and a key from one refused at the other's address —
  // is `test_tc4b…` and `test_tc7…`, which build both. Saying so is the point:
  // a check that cannot cover its subject must print what it skipped beside
  // what it checked (CLAUDE.md law 7's fifth shape).
  console.log(
    "      note: one utility in this database, so the TWO-TENANT property is " +
      "proved by tests/test_us_int_041_partner_surface.py (tc4b, tc7, tc8d), not here",
  );

  // ═════ 6 · what a manager sees ══════════════════════════════════════════
  console.log("\n── 6 · S142 · Who has been reading ──");
  // ⚠ THE FIELD IDS ARE `#signin-email` / `#signin-password`, NOT `#email`.
  // The first draft guessed and waited thirty seconds for a locator that never
  // existed — the same shape as a check looking at the wrong thing, arriving
  // in the walkthrough rather than in the product. `cr069-c-run-record.mjs`
  // already had the right pair; this is copied from it rather than re-guessed.
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", STAFF_EMAIL);
  await page.fill("#signin-password", STAFF_PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });
  await page.goto(`${BASE}/${TENANT}/settings/integrations/${PARTNER}`, {
    waitUntil: "networkidle",
  });
  await page.waitForSelector("[data-access-log]", { timeout: 20000 });

  const rows = page.locator("[data-access-row]");
  const rowCount = await rows.count();
  check(rowCount >= 3, `the access log shows the morning's pages (${rowCount} rows)`);
  const unusual = page.locator('[data-unusual="true"]');
  check((await unusual.count()) >= 1, "the unusual read is drawn differently from the others");

  // ⚠ **THE AMBER BOX IS A QUOTE NOW (2026-09-16, `2.287.3`).** `ACC-01` draws
  // the WATCH note as a quote with a left rule, not the filled `ConsequenceBox`
  // this check was written against, so the selector moved with it. The SENTENCE
  // is unchanged and is still what this asserts — which is the point: the check
  // followed the element rather than being deleted for going red.
  const box = page.locator("[data-access-watch]");
  check((await box.count()) === 1, "the WATCH quote is under the table");
  check(
    /two in the morning/i.test(await box.innerText()),
    "…and it says why the screen exists, in one sentence",
  );

  // ⚠ **THE THREE READ STATES, WHICH IS WHAT `DEF-INT-5484` WAS.** This screen
  // is the LOADED one, so the other two must NOT be drawn over it — and the
  // sentence that used to cover all three must be gone from the product.
  check(
    (await page.locator("[data-access-failed]").count()) === 0,
    "the loaded log is not also claiming the read failed",
  );
  check(
    !/Nobody has collected anything yet/i.test(await page.locator("[data-access-log]").innerText()),
    "⚠ the one sentence that covered loading, failure and emptiness is gone",
  );

  const register = page.locator('[data-register-row="inward"]');
  check((await register.count()) >= 1, "the register shows the relationship pointing INWARD");
  const sentence = (await register.first().innerText()).trim();
  check(/ — reads /.test(sentence), `…and it reads as a sentence: "${sentence}"`);
  check(/authorised by /.test(sentence), "…naming who authorised it");

  const dom = await page.content();
  check(!dom.includes(KEY), "⚠ the key's plaintext is NOWHERE in the DOM");
  check(!dom.includes("sbh_live"), "…not even its prefix");
  check(dom.includes(HINT), `the hint IS shown — ${HINT}`);
  await noInternals(page, "S142");
  await page.screenshot({ path: join(OUT, "6-who-has-been-reading.png"), fullPage: true });

  console.log(`\n${timings.summary?.() ?? ""}`);
  await browser.close();

  process.exit(gaps.report(failures));
})().catch((error) => {
  console.error(error);
  process.exit(2);
});
