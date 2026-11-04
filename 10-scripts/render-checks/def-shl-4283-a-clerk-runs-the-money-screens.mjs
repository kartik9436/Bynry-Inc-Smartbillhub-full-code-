/**
 * RENDERED-OUTPUT CHECK — DEF-SHL-4283, in a real browser, against the running
 * product. **A BILLING CLERK RUNS A REPORT AND OPENS THE REFUNDS QUEUE.**
 *
 * ⚠ **WHY THIS IS A SECOND FILE AND NOT SIX MORE LINES IN THE FIRST ONE.**
 * `def-shl-4272-a-clerk-signs-in-and-clicks.mjs` is the repository's first
 * walkthrough that signs in as anybody but an administrator, and it is
 * deliberately BORING: it clicks six screens and asks whether the product drew
 * at all, because the defect it exists for was the whole product being one
 * error sentence. This one asks a narrower question that only became visible
 * once that was fixed: **does the clerk get the tenant's own accounting
 * period** — and its six screens are a different six, chosen because they are
 * the ones that broke.
 *
 * The handoff's lesson from `DEF-SHL-4272` was *"a walkthrough per ROLE, not
 * only per screen"*. Two files at one role is that lesson made real: the first
 * walks the role's ordinary day, this one walks what the role's day needs from
 * a permission it does not hold.
 *
 * ── THE DEFECT, IN THE CLERK'S OWN WORDS ──────────────────────────────────
 * `Reports → By premises` (A4 `reports`, Clerk **Run**) said *"Set the fiscal
 * year start to see the current period."* — at a tenant whose fiscal year start
 * IS set, pointing at a screen only a System Admin can open — and the report
 * was never requested at all, because the screen gates the request on the
 * period. `Payments → Refunds` (A4 `payments_record`, Clerk **Full**, the
 * screen a clerk RAISES refunds on) drew the same sentence in its header.
 *
 * Both read `GET /settings/regional`, which is `SettingsReadAnyWriteSystemAdmin`
 * — `{system_admin, executive}` — so for a clerk it answers `403 AUTH-002`.
 * That is `DEF-SHL-4272` surviving in a narrower form: the shell's two boot
 * reads were moved to `GET /shell/display` and these were not.
 *
 * ── HOW TO RUN IT — VERIFIED END TO END ON 2026-09-06 ─────────────────────
 *   The defaults below are `seed_demo`'s OWN values, so a freshly seeded
 *   database needs no env at all except `SMOKE_BASE`:
 *
 *     createdb sbh_shl4283
 *     export DB="postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_shl4283"
 *     export DJANGO_SETTINGS_MODULE=config.settings.local
 *     (cd 06-backend && DATABASE_URL=$DB python3 manage.py migrate --noinput)
 *     (cd 06-backend && DATABASE_URL=$DB python3 manage.py seed_demo)
 *
 *   ⚠ **THEN GIVE THE TENANT A CLERK, AND THE FACT THAT YOU HAVE TO IS PART OF
 *   THIS DEFECT'S STORY.** `seed_demo` creates exactly ONE user — the System
 *   Admin — and `apps/identity/sample_data.py` leaves any other role INVITED
 *   AND UNCREDENTIALED. So there was never a signed-in clerk to click as, which
 *   is a large part of why a total lockout survived a green suite for sixteen
 *   days. `def-shl-4283-fixture.py` beside this file makes one, idempotently:
 *
 *     PYTHONPATH=06-backend DATABASE_URL=$DB \
 *       python3 10-scripts/render-checks/def-shl-4283-fixture.py
 *
 *     (cd 06-backend && DATABASE_URL=$DB python3 manage.py runserver 127.0.0.1:8141 --noreload &)
 *     (cd 07-frontend && npx vite build && \
 *        PORT=4341 API_PROXY_TARGET=http://127.0.0.1:8141 node server.mjs &)
 *     SMOKE_BASE=http://127.0.0.1:4341 \
 *       node 10-scripts/render-checks/def-shl-4283-a-clerk-runs-the-money-screens.mjs
 *
 * ⚠ **REBUILD THE BUNDLE. DO NOT TRUST A RUNNING ONE** — a stale `dist` from
 * another lane looks exactly like a fix that did not work.
 *
 * ── WHAT IT DOES ──────────────────────────────────────────────────────────
 *   0  Sign in as the seeded BILLING CLERK.
 *   1  Prove the wire: `GET /shell/display` answers 200 and carries a `period`
 *      of exactly five fields, and `close_by` is NOT one of them.
 *   2  `Reports → By premises` — the false sentence is gone AND the report was
 *      actually requested (the network is watched, because a missing sentence
 *      is not a running report).
 *   3  `Payments → Refunds` — the header carries the tenant's period.
 *   4  Prove the SETTINGS SURFACE IS STILL SHUT. A run where 2 and 3 pass and
 *      this fails means somebody widened the settings gate and re-opened
 *      `DEF-196`.
 *   5  Nothing was taken from the System Admin: the same two screens, plus the
 *      hand-off deadline the clerk correctly does not get.
 */
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
import { join } from "node:path";

// `playwright-core` lives in 07-frontend/node_modules, and `createRequire` on
// this file's own URL would look beside the SCRIPT. Resolve from the frontend
// package instead, exactly as `npm run e2e` would.
const require = createRequire(new URL("../../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright-core");

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4341";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const CLERK_EMAIL = process.env.SMOKE_CLERK_EMAIL ?? "sam.reyes@sample.test";
const CLERK_PASSWORD = process.env.SMOKE_CLERK_PASSWORD ?? "Cl3rk!passw0rd";
const ADMIN_EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const ADMIN_PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const SHOTS = process.env.SMOKE_OUT ?? "/tmp/def-shl-4283";

/**
 * ⚠ THE SENTENCE THE WHOLE DEFECT REDUCES TO, and it is worth reading twice:
 * it is not an error message, it is a perfectly calm instruction that happens
 * to be FALSE and to point somewhere the reader may not go.
 */
const FALSE_SENTENCE = "Set the fiscal year start to see the current period";
/** The shell's own failure state — the parent defect, watched for here too. */
const SHELL_FAILURE = "We couldn't load your regional settings";

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

async function signIn(page, email, password) {
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", email);
  await page.fill("#signin-password", password);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
}

/**
 * Open a path, and report what the page IS as well as what it asked the server.
 *
 * ⚠ **THE REQUEST LIST IS HALF THE CHECK AND IT IS THE HALF A SCREENSHOT
 * CANNOT GIVE YOU.** `Reports → By premises` gates its report on the period, so
 * for a clerk the screen looked calm and simply never asked. "The sentence is
 * gone" and "the report ran" are two different claims.
 */
async function open(page, path) {
  const requests = [];
  const listener = (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith("/api/")) requests.push(url.pathname + url.search);
  };
  page.on("request", listener);
  await page.goto(`${BASE}${path}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(900);
  page.off("request", listener);
  const state = await page.evaluate(
    ([falseSentence, shellFailure]) => {
      const text = (document.body.textContent ?? "").trim();
      return {
        falseSentence: text.includes(falseSentence),
        shellFailed: text.includes(shellFailure),
        heading: document.querySelector("h1")?.textContent?.trim() ?? null,
        rollup: document.querySelector(".page-header-rollup")?.textContent?.trim() ?? null,
        chars: text.length,
      };
    },
    [FALSE_SENTENCE, SHELL_FAILURE],
  );
  return { ...state, requests };
}

async function main() {
  mkdirSync(SHOTS, { recursive: true });
  const executablePath =
    process.env.SMOKE_CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
  const browser = await chromium.launch({ executablePath });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();

  console.log("\n── 0 · sign in as the BILLING CLERK ──");
  await signIn(page, CLERK_EMAIL, CLERK_PASSWORD);
  console.log(`   signed in to ${TENANT} as ${CLERK_EMAIL}`);

  console.log("\n── 1 · the wire: /shell/display carries a period and no close policy ──");
  const boot = await page.evaluate(async (tenant) => {
    const r = await fetch(`/api/${tenant}/shell/display`, { credentials: "include" });
    const body = r.ok ? await r.json() : null;
    return {
      status: r.status,
      hasPeriod: body ? body.period !== undefined : false,
      period: body?.period ?? null,
      keys: body?.period ? Object.keys(body.period) : [],
    };
  }, TENANT);
  // ⚠ GATED ON THE 200. Without it, a stack where the route does not exist
  // answers 404, `keys` is empty, and "no close_by here" ticks cheerfully over
  // nothing — law 7's *structurally incapable of failing*, and the shape the
  // sibling walkthrough was caught by on exactly this assertion.
  check(boot.status === 200, `GET /shell/display answers ${boot.status} to a clerk (want 200)`);
  check(
    boot.status === 200 && boot.hasPeriod && boot.period !== null,
    `and it carries the tenant's period: ${boot.period ? JSON.stringify(boot.period) : "(absent or null — this tenant has no fiscal year start, or the fix is not in this build)"}`,
  );
  check(
    boot.status === 200 && boot.keys.length === 5 && !boot.keys.includes("close_by"),
    `the card is the five DRAWING fields and not the close deadline — keys: ` +
      `${boot.keys.length ? boot.keys.join(", ") : "(none)"}`,
  );

  console.log("\n── 2 · Reports → By premises — the report a clerk may RUN ──");
  const report = await open(page, `/${TENANT}/reports/by-premises`);
  await page.screenshot({ path: join(SHOTS, "clerk-by-premises.png"), fullPage: true });
  check(!report.shellFailed, `the screen does NOT show "${SHELL_FAILURE}"`);
  check(
    !report.falseSentence,
    `it does NOT tell the clerk "${FALSE_SENTENCE}" — the tenant's start IS set` +
      (report.falseSentence ? " ⟵ THIS IS THE DEFECT" : ""),
  );
  const ran = report.requests.filter((p) => p.includes("by_premises"));
  check(
    ran.length > 0,
    `and the report was actually REQUESTED — ${ran.length ? ran.join(" · ") : "IT WAS NOT: the screen gated on a period it could not read"}`,
  );

  console.log("\n── 3 · Payments → Refunds — the screen a clerk RAISES refunds on ──");
  const refunds = await open(page, `/${TENANT}/finance/refunds`);
  await page.screenshot({ path: join(SHOTS, "clerk-refunds.png"), fullPage: true });
  check(!refunds.shellFailed, `the screen does NOT show "${SHELL_FAILURE}"`);
  check(!refunds.falseSentence, `it does NOT tell the clerk "${FALSE_SENTENCE}"`);
  check(
    refunds.rollup !== null && /Period\s+\d/.test(refunds.rollup ?? ""),
    `and its header names the tenant's period — rollup reads: ${refunds.rollup ?? "(no rollup drawn)"}`,
  );

  console.log("\n── 4 · and Settings is STILL shut to them (the fix is a separation) ──");
  // ⚠ A RUN WHERE 2 AND 3 PASS AND THIS FAILS MEANS SOMEBODY WIDENED THE
  // SETTINGS GATE AND RE-OPENED DEF-196. A4 gives a Billing Clerk no
  // `settings_lookups` cell and US-TEN-009 TC-5 has said so since the surface
  // was built.
  const refused = await page.evaluate(async (tenant) => {
    const r = await fetch(`/api/${tenant}/settings/regional`, { credentials: "include" });
    return r.status;
  }, TENANT);
  check(refused === 403, `GET /settings/regional answers ${refused} to a Billing Clerk (want 403)`);

  console.log("\n── 5 · nothing was taken away from the System Admin ──");
  await context.clearCookies();
  await signIn(page, ADMIN_EMAIL, ADMIN_PASSWORD);
  const adminReport = await open(page, `/${TENANT}/reports/by-premises`);
  check(
    !adminReport.shellFailed && !adminReport.falseSentence,
    "the admin's by-premises report still draws",
  );
  const owner = await page.evaluate(async (tenant) => {
    const r = await fetch(`/api/${tenant}/settings/regional`, { credentials: "include" });
    const body = r.ok ? await r.json() : null;
    return { status: r.status, closeBy: body?.current_period?.close_by ?? null };
  }, TENANT);
  check(owner.status === 200, `GET /settings/regional answers ${owner.status} to the owner (want 200)`);
  // The field the clerk correctly does NOT receive is still served to the role
  // whose cell it belongs to. Its absence upstream is a decision, not a loss.
  check(
    owner.status === 200 && "closeBy" in owner,
    `and the admin still gets the hand-off deadline: close_by = ${owner.closeBy ?? "null (this tenant sets no close day)"}`,
  );

  await browser.close();

  console.log("\n────────────────────────────────────────────────────────────");
  console.log(`screenshots: ${SHOTS}`);
  if (failures.length === 0) {
    console.log("PASS — a Billing Clerk gets the tenant's period, and Settings is still shut.");
    process.exit(0);
  }
  console.log(`FAIL — ${failures.length} check(s):`);
  for (const f of failures) console.log(`  ⛔ ${f}`);
  process.exit(1);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
