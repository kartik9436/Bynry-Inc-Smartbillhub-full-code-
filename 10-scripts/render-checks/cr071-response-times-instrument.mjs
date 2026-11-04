/**
 * RENDERED-OUTPUT CHECK — CR-071, the response-time instrument, proved against
 * a running product.
 *
 * ⚠ **WHY THIS EXISTS.** `11-response-times.md` §5 obliges every portal
 * endpoint's walkthrough to *"record the measured time and print it, rather
 * than asserting that a target was met"*. `lib/timings.mjs` is the thing that
 * does it. **The portal does not exist yet** — `CR-068` wave A is the first
 * wave and later waves build the customer screens — so there is no portal
 * endpoint to point the instrument at. Hard-won law 6 says a unit test over a
 * fake array is not proof that a tool works; only a running product is. So this
 * runs the instrument against the **staff app**, which exists, and prints its
 * real numbers.
 *
 * **IT IS A PROOF OF THE INSTRUMENT, NOT A SPECIFICATION FOR THE STAFF APP.**
 * §6 of the specification is explicit: *"Anything about the staff app. Its
 * targets are its own; this file only forbids the portal from spending them."*
 * Nothing here is a staff-app budget and no figure below may be quoted as one.
 * The two targets at the end are marked DEMONSTRATION and exist to prove that a
 * miss prints as a miss.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   # against a database nobody else is seeding
 *   su postgres -c "psql -c 'create database sbh_cr071 owner smartbillhub'"
 *   export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
 *     DATABASE_URL="postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_cr071?sslmode=disable"
 *   (cd 06-backend && python manage.py migrate --no-input && python manage.py seed_demo \
 *      && python manage.py load_sample_data --tenant brazosbend)
 *   (cd 06-backend && python manage.py runserver 127.0.0.1:8091 --noreload &)
 *   (cd 07-frontend && ./node_modules/.bin/vite build && \
 *      PORT=4291 API_PROXY_TARGET=http://127.0.0.1:8091 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4291 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr071-response-times-instrument.mjs
 *
 * ── WHAT IT PROVES ────────────────────────────────────────────────────────
 *   1  The recorder attaches to a BrowserContext and catches API responses the
 *      SPA made on its own — nothing is hand-listed.
 *   2  Two screens opened ONCE each produce rows whose p95 is marked `!` and
 *      called out in words: *"NOT A p95 — n=1, so this is simply the slowest of
 *      1"*. That is the trap §5 is about, printed rather than hidden.
 *   3  The same screen asked for 25 times produces a p95 whose marker CHANGES —
 *      it stops being the maximum. The instrument's honesty is a function of
 *      the sample, and this shows the function moving.
 *   4  A target comparison prints the MEASURED figure first, and a deliberate
 *      miss reads *"OVER by N ms"* rather than being rounded away.
 *   5  The run exits 0 whatever the numbers are — §5 asks for a report, and an
 *      instrument that can fail a build on latency is the assertion it replaces.
 *      This script fails only if the instrument itself did not work.
 *
 * ── Trace ──────────────────────────────────────────────
 * Rules:   `CR-071` · `11-response-times.md` §5, §6 · law 6 (diff the running
 *          app; no gate looks at rendered output) · law 7
 * Tests:   `10-scripts/tests/test_cr071_timings.mjs` covers the arithmetic;
 *          this covers that it works on a real browser against a real server
 * ───────────────────────────────────────────────────────
 */

import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { join } from "node:path";

import { attachTimings } from "./lib/timings.mjs";

const require = createRequire(join(process.cwd(), "07-frontend", "package.json"));
const { chromium } = require("playwright-core");

function resolveChromium() {
  const wanted = chromium.executablePath();
  try {
    execFileSync(wanted, ["--version"], { stdio: "ignore" });
    return wanted;
  } catch {
    const root = process.env.PLAYWRIGHT_BROWSERS_PATH ?? "/opt/pw-browsers";
    for (const dir of require("node:fs").readdirSync(root)) {
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4290";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const REPEATS = Number(process.env.SMOKE_REPEATS ?? 25);
const VIEWPORT = { width: 1440, height: 1000 };

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();

  console.log(`cr071: ${BASE} tenant=${TENANT} — proving lib/timings.mjs on the STAFF app`);
  console.log("        (the portal has no screens yet; §6: the staff app has no targets of its own)");

  const timings = attachTimings(context);

  // ═════ sign in — a real round trip, kept in the table on purpose ══════════
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
  console.log("   signed in");

  // ═════ 1 · two screens, once each — the small-sample case ════════════════
  console.log("\n── two screens, opened ONCE each ──");
  for (const path of ["/accounts", "/customers"]) {
    await page.goto(`${BASE}/${TENANT}${path}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(500);
    console.log(`   opened ${path}`);
  }

  const single = await timings.report({
    title: "one click each — what a walkthrough normally has",
  });
  check(single.rows.length > 0, `the recorder caught ${single.rows.length} endpoint(s) nobody hand-listed`);
  const thin = single.rows.filter((r) => r.honesty.p95.marker === "!");
  check(
    thin.length > 0,
    `${thin.length} row(s) say in words that their p95 is not a p95 — the §5 trap, printed`,
  );

  // ═════ 2 · the same screen 25 times — a p95 that is a p95 ════════════════
  console.log(`\n── the accounts list, asked for ${REPEATS} times ──`);
  timings.reset();
  for (let i = 0; i < REPEATS; i += 1) {
    await page.goto(`${BASE}/${TENANT}/accounts`, { waitUntil: "networkidle" });
  }

  const repeated = await timings.report({
    title: `the accounts list × ${REPEATS} — the same instrument, a sample worth quoting`,
    targets: [
      // ⚠ DEMONSTRATION ONLY. The staff app has no response-time targets and
      // these are not proposals for any. They are here to prove both branches
      // of the comparison print: one that is met and one that is not.
      { id: "DEMO-under", match: "/api/", p95: 2000 },
      { id: "DEMO-over", match: "/api/", p95: 5 },
    ],
  });

  const busiest = repeated.rows.find((r) => r.n >= 20);
  check(
    busiest !== undefined,
    busiest
      ? `${busiest.key} has n=${busiest.n}, so its p95 is the ${busiest.honesty.p95.rank}th of ${busiest.n} and no longer the maximum`
      : `no endpoint reached 20 samples over ${REPEATS} reloads — the repeat loop did not exercise one`,
  );
  if (busiest) {
    check(
      busiest.honesty.p95.marker !== "!",
      `its p95 marker is "${busiest.honesty.p95.marker || "none"}" — it stopped being the maximum, which is the whole point`,
    );
  }
  check(
    repeated.misses.length > 0,
    `${repeated.misses.length} target miss(es) reported as misses rather than rounded away (§5)`,
  );

  timings.detach();
  await browser.close();

  if (failures.length > 0) {
    console.log(`\n⛔ ${failures.length} failure(s) — the INSTRUMENT is broken, not the app`);
    for (const f of failures) console.log(`   · ${f}`);
    process.exit(1);
  }
  console.log("\n✓ cr071: the instrument records, groups, and says what its own numbers are worth");
  console.log("  (no figure above is a staff-app target, and none of it proves anything under load)");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
