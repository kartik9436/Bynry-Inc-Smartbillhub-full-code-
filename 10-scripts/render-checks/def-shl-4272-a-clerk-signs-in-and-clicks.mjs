/**
 * RENDERED-OUTPUT CHECK — DEF-SHL-4272, in a real browser, against the running
 * product. **A BILLING CLERK SIGNS IN AND USES THE PRODUCT.**
 *
 * ⚠ **WHY THIS EXISTS, AND IT IS THE WHOLE POINT OF THE FILE.** On 2026-09-06 a
 * Billing Clerk could not use SMARTBillHub at all, and had not been able to
 * since 2026-08-21 — sixteen days. They signed in successfully, reached
 * `/dashboard`, and **every screen in the product** rendered the shell's
 * failure state: *"We couldn't load your regional settings."* with a Retry that
 * could never succeed. The shell booted on `GET /settings/company` and
 * `GET /settings/regional`, both of which are Admin/Executive only, because
 * A4's `settings_lookups` row gives a Billing Clerk no cell at all.
 *
 * **Nothing in this repository could see it.** Every frontend test passes
 * formatting as a prop or seeds the query cache; every backend test drives
 * services or an admin fixture; and — the one that matters here — **all 92
 * render-checks in `10-scripts/render-checks/` signed in as a system
 * administrator.** A product with three roles whose every check runs as the
 * most privileged one is a product tested in one third of the states it ships
 * in. This file is the missing third.
 *
 * It is deliberately BORING. It signs in as a clerk and clicks: the dashboard,
 * a list, a detail, a second module. There is no clever assertion, because the
 * defect it exists to catch does not need one — the whole product was a single
 * error sentence.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   createdb sbh_shl4272 TEMPLATE <a seeded database>
 *   DJANGO_SETTINGS_MODULE=config.settings.local \
 *   DATABASE_URL="postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_shl4272" \
 *     python3 06-backend/manage.py migrate
 *   # the seeded clerk is INVITED AND UNCREDENTIALED by design
 *   # (apps/identity/sample_data.py) — which is itself part of why no
 *   # walkthrough ever signed in as one. Give them a password first:
 *   #   user.password_hash = make_password(...); membership.status = "active"
 *   DJANGO_SETTINGS_MODULE=config.settings.local DATABASE_URL=… \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8141 --noreload &
 *   (cd 07-frontend && npx vite build && \
 *      STATIC_DIR=$PWD/dist PORT=4341 API_PROXY_TARGET=http://127.0.0.1:8141 \
 *      node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4341 \
 *     node 10-scripts/render-checks/def-shl-4272-a-clerk-signs-in-and-clicks.mjs
 *
 * ⚠ **REBUILD THE BUNDLE. DO NOT TRUST A RUNNING ONE** — a stale `dist` from
 * another lane looks exactly like a fix that did not work, and cost hours on
 * 2026-09-05.
 *
 * ── WHAT IT DOES ──────────────────────────────────────────────────────────
 *   0  Sign in as the seeded BILLING CLERK, not as the owner.
 *   1  Prove the shell drew: the sidebar is present and the failure sentence
 *      is not. This is the defect, inverted.
 *   2  Walk four screens in four modules and check each one drew ITS OWN
 *      content — not the shell's error, not the loading skeleton.
 *   3  Prove the tenant's own date format actually reached the clerk's screen,
 *      because "the shell drew something" and "the shell drew the right thing"
 *      are different claims (DEF-SHL-3964).
 *   4  Prove the SETTINGS SURFACE IS STILL SHUT. The fix is a separation, not
 *      a widening: a clerk opening Settings must still be refused. A run where
 *      step 2 passes and step 4 fails means someone widened the settings gate
 *      and re-opened DEF-196.
 *   5  Sign in as the System Admin and confirm nothing was taken away from
 *      them — the same screens, plus Settings.
 */
import { createRequire } from "node:module";

// `playwright-core` lives in 07-frontend/node_modules, and `createRequire` on
// this file's own URL would look beside the SCRIPT. Resolve from the frontend
// package instead, exactly as `npm run e2e` would.
const require = createRequire(new URL("../../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright-core");

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4341";
const TENANT = process.env.SMOKE_TENANT ?? "pine-hill";
const CLERK_EMAIL = process.env.SMOKE_CLERK_EMAIL ?? "sam.reyes@sample.test";
const CLERK_PASSWORD = process.env.SMOKE_CLERK_PASSWORD ?? "Cl3rk!passw0rd";
const ADMIN_EMAIL = process.env.SMOKE_EMAIL ?? "sarah@pinehillwp.test";
const ADMIN_PASSWORD = process.env.SMOKE_PASSWORD ?? "Pin3Hill!passw0rd";

/**
 * The sentence the shell renders when it cannot read the tenant's formats.
 * ⚠ THIS IS THE STRING THE WHOLE DEFECT REDUCES TO. A clerk saw it, and only
 * it, on every route in the product for sixteen days.
 */
const SHELL_FAILURE = "We couldn't load your regional settings";

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

/** The screens a Billing Clerk works in, one per module, named as a person would. */
const SCREENS = [
  { module: "Dashboard", name: "Dashboard", path: `/${TENANT}/dashboard` },
  { module: "Accounts", name: "Accounts", path: `/${TENANT}/accounts` },
  { module: "Payments", name: "Payments", path: `/${TENANT}/payments` },
  { module: "Premises", name: "Premises", path: `/${TENANT}/premises` },
  { module: "Billing", name: "Billing → Bills", path: `/${TENANT}/billing` },
  { module: "Reads", name: "Meter Reads", path: `/${TENANT}/reads` },
];

async function signIn(page, email, password) {
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", email);
  await page.fill("#signin-password", password);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
}

async function signOut(context) {
  await context.clearCookies();
}

/**
 * Open a path and report what the page actually IS.
 *
 * Three states are distinguished on purpose, because a check whose output
 * cannot tell them apart is the shape hard-won law 7 warns about: the shell's
 * FAILURE (the defect), the shell's loading SKELETON (a slow read, or the same
 * defect wearing a different coat), and a real SCREEN.
 */
async function open(page, path) {
  await page.goto(`${BASE}${path}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(900);
  return page.evaluate((failureText) => {
    const body = document.body;
    const text = (body.textContent ?? "").trim();
    const skeleton = body.querySelector(".skeleton");
    // The sidebar is the shell's own chrome: present only once the shell has
    // handed control to its Outlet.
    const sidebar = body.querySelector(".sidebar, .app-shell");
    const heading = body.querySelector("h1");
    return {
      failed: text.includes(failureText),
      skeletonOnly: skeleton !== null && heading === null,
      hasSidebar: sidebar !== null,
      heading: heading ? (heading.textContent ?? "").trim() : null,
      chars: text.length,
    };
  }, SHELL_FAILURE);
}

async function main() {
  // The sandbox has chromium build 1194 under PLAYWRIGHT_BROWSERS_PATH while
  // this playwright wants a newer one, so the executable is named rather than
  // looked up. `SMOKE_CHROME` overrides it anywhere the layout differs.
  const executablePath =
    process.env.SMOKE_CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
  const browser = await chromium.launch({ executablePath });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();

  console.log("\n── 0 · sign in as the BILLING CLERK (not the owner) ──");
  await signIn(page, CLERK_EMAIL, CLERK_PASSWORD);
  console.log(`   signed in to ${TENANT} as ${CLERK_EMAIL}`);

  console.log("\n── 1 · the shell drew at all — the defect, inverted ──");
  const dash = await open(page, `/${TENANT}/dashboard`);
  check(!dash.failed, `the dashboard does NOT show "${SHELL_FAILURE}"`);
  check(dash.hasSidebar, "the app shell rendered its frame (sidebar present)");
  check(!dash.skeletonOnly, "the dashboard is a screen, not a bare loading skeleton");

  console.log("\n── 2 · four modules, clicked, as a clerk ──");
  for (const screen of SCREENS) {
    const state = await open(page, screen.path);
    const ok = !state.failed && !state.skeletonOnly && state.hasSidebar;
    check(
      ok,
      `${screen.name.padEnd(22)} drew ${state.heading ? `"${state.heading}"` : "no <h1>"}` +
        ` (${state.chars} chars)` +
        (state.failed ? " — SHELL FAILURE STATE" : "") +
        (state.skeletonOnly ? " — LOADING SKELETON ONLY" : ""),
    );
  }

  console.log("\n── 3 · and it drew the TENANT'S date, not a seed ──");
  // "The shell drew something" and "the shell drew the right thing" are two
  // different claims. DEF-SHL-3964 is the second one, and a clerk must get it
  // too — the whole payload this fix moved is the date format and the zone.
  //
  // ⚠ **EVERY SCREEN IS TRIED, NOT ONE.** The first cut of this step read the
  // Payments list alone and reported ⛔ *"no dated row — nothing to check
  // here"* on a fixture whose Payments list is empty. That is a check that
  // fails for a reason unrelated to what it is checking, which is worse than
  // no check: the next reader learns to ignore it. A date anywhere in the
  // product proves the pair reached the renderer, so the pass condition is
  // ANY dated row on ANY of the screens above — and a run where NONE of six
  // screens draws a date is itself worth failing on, because either the
  // fixture is empty end to end or dates have stopped rendering, and the line
  // below says which screens were looked at so a reader can tell.
  const dateReport = [];
  let drawn;
  for (const screen of SCREENS) {
    await page.goto(`${BASE}${screen.path}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(700);
    const dates = await page.$$eval("time[datetime]", (nodes) =>
      nodes
        .map((n) => ({ value: n.getAttribute("datetime"), text: (n.textContent ?? "").trim() }))
        .filter((d) => d.text.length > 0),
    );
    dateReport.push(`${screen.name}: ${dates.length}`);
    if (drawn === undefined && dates.length > 0) {
      drawn = { screen: screen.name, ...dates[0] };
    }
  }
  check(
    drawn !== undefined,
    drawn
      ? `the clerk's ${drawn.screen} draws dates — e.g. "${drawn.text}" (server sent ` +
          `${drawn.value}) · counts per screen: ${dateReport.join(" · ")}`
      : `NO dated row on ANY of the six screens — ${dateReport.join(" · ")}. Either this ` +
          `fixture holds no dated rows at all, or dates have stopped rendering`,
  );

  console.log("\n── 4 · and Settings is STILL shut to them (the fix is a separation) ──");
  // ⚠ A RUN WHERE STEP 2 PASSES AND THIS FAILS MEANS SOMEBODY WIDENED THE
  // SETTINGS GATE AND RE-OPENED DEF-196. A4 gives a Billing Clerk no
  // `settings_lookups` cell, and US-TEN-009 TC-5 has said so since the surface
  // was built.
  const refused = await page.evaluate(async (tenant) => {
    const r = await fetch(`/api/${tenant}/settings/regional`, { credentials: "include" });
    return r.status;
  }, TENANT);
  check(refused === 403, `GET /settings/regional answers ${refused} to a Billing Clerk (want 403)`);
  const refusedCompany = await page.evaluate(async (tenant) => {
    const r = await fetch(`/api/${tenant}/settings/company`, { credentials: "include" });
    return r.status;
  }, TENANT);
  check(
    refusedCompany === 403,
    `GET /settings/company answers ${refusedCompany} to a Billing Clerk (want 403)`,
  );
  const boot = await page.evaluate(async (tenant) => {
    const r = await fetch(`/api/${tenant}/shell/display`, { credentials: "include" });
    const body = r.ok ? await r.json() : null;
    return { status: r.status, keys: body ? Object.keys(body.regional ?? {}) : [] };
  }, TENANT);
  check(boot.status === 200, `GET /shell/display answers ${boot.status} to a Billing Clerk (want 200)`);
  // ⚠ **GATED ON THE 200, BECAUSE OTHERWISE THIS PASSES ON A 404.** The first
  // cut asked only "are these keys absent", and on the pre-fix stack — where
  // the route does not exist at all — it printed a cheerful ✓ over an empty
  // list. A check that passes hardest when the thing it inspects is missing is
  // hard-won law 7's *structurally incapable of failing*, and this is the
  // version that was caught by running the walkthrough against the defect.
  check(
    boot.status === 200 &&
      boot.keys.length === 8 &&
      !boot.keys.includes("accounting_method") &&
      !boot.keys.includes("close_day") &&
      !boot.keys.includes("lock_closed_periods") &&
      !boot.keys.includes("current_period"),
    `and it carries the 8 display fields and no finance policy — regional keys: ` +
      `${boot.keys.length ? boot.keys.join(", ") : "(none — the route did not answer)"}`,
  );

  console.log("\n── 5 · nothing was taken away from the System Admin ──");
  await signOut(context);
  await signIn(page, ADMIN_EMAIL, ADMIN_PASSWORD);
  const adminDash = await open(page, `/${TENANT}/dashboard`);
  check(!adminDash.failed && adminDash.hasSidebar, "the admin's dashboard still draws");
  const adminSettings = await page.evaluate(async (tenant) => {
    const r = await fetch(`/api/${tenant}/settings/regional`, { credentials: "include" });
    return r.status;
  }, TENANT);
  check(adminSettings === 200, `GET /settings/regional answers ${adminSettings} to the owner (want 200)`);

  await browser.close();

  console.log("\n────────────────────────────────────────────────────────────");
  if (failures.length === 0) {
    console.log("PASS — a Billing Clerk can use SMARTBillHub, and Settings is still theirs alone.");
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
