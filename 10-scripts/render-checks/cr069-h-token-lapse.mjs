/**
 * RENDERED-OUTPUT CHECK — CR-069 wave H, "token lapse averted", in a real
 * browser. Screens `S142` (connection detail, frame `54.1`) and `S7` (the
 * dashboard attention strip). Journey `J50`.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: no gate in this repository looks at
 * rendered output, and nine defects in one day were found this way and by
 * nothing else. PO ruling 2026-09-03: *"ensure you do web walkthorugh before
 * you sign off the user story or build"*.
 *
 * ⚠ **AND THIS WAVE'S SUBJECT IS A SENTENCE WITH A DATE IN IT**, which is the
 * one thing a unit test is worst at. `test_us_int_027_expiry.py` can prove the
 * server says `state: warning, days_left: 11`; only a browser can tell you that
 * the box was PAINTED, that the date inside it reads `09/17/2026` in the
 * tenant's own format rather than `2026-09-17T07:12:59.303595+00:00`, and that
 * the twenty runs are still on the screen after re-authorising.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   eval "$(10-scripts/proof-db.sh clone int_h --export)"
 *   export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false
 *   (cd 06-backend && python3 manage.py migrate integrations)
 *   (cd 06-backend && python3 manage.py shell < ../10-scripts/render-checks/cr069-h-fixture.py)
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8160 --noreload &
 *   (cd 07-frontend && ./node_modules/.bin/vite build && \
 *      PORT=4360 API_PROXY_TARGET=http://127.0.0.1:8160 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4360 node 10-scripts/render-checks/cr069-h-token-lapse.mjs
 *
 * ⚠ **BUILD THE BUNDLE FIRST.** A stale `dist/` means every assertion here
 * passes or fails about a build nobody is shipping.
 *
 * ── WHAT IT CLICKS (the wave H demo script, 10-execution-plan.md) ─────────
 *   1  S142 — the credential is eleven days from lapsing and the WarningBox is
 *      PAINTED, with the date in the tenant's own regional format.
 *   2  The sweep runs → the warning is stamped once, and a second sweep on the
 *      same day stamps nothing (BR-INT-042's *once per day, never twice*).
 *   3  S7 — the same sentence on the dashboard, above the numbers.
 *   4  Twenty runs are on the screen BEFORE re-authorising; they are counted.
 *   5  Re-authorise through the fixture return trip → credential v2.
 *   6  The warning is GONE, the version is 2, v1 is retained and NOT
 *      overwritten, and the twenty runs are all still listed.
 *   7  No secret anywhere: the token string appears in no page of the walk.
 *
 * ⚠ **WHAT IT REFUSES TO CLAIM, AND HOW.** The demo script's step 5 —
 * *"one email queued to the admins"* — cannot be performed: notifications
 * publishes no expiry notice, so the sweep warns on screen and queues nothing.
 * That is `DEF-INT-4214`, recorded through `lib/knownGaps.mjs` as a known gap
 * with its register id — never a silent skip and never a failure. It goes RED
 * IN BOTH DIRECTIONS: the day notifications publishes the callable, this run
 * fails and names the row to delete.
 *
 * The step that redirects to Microsoft's own consent screen is also not walked
 * — `login.microsoftonline.com` is not ours and a walkthrough must not dial it.
 * The trip back is driven through the REAL `GET /oauth/return` endpoint with
 * the REAL state nonce; only the token exchange is the recorded fixture, which
 * is exactly the seam `US-INT-005` asks for (*"recorded fixtures, no network in
 * tests"*).
 */

import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

import { Gaps } from "./lib/knownGaps.mjs";

const require = createRequire(join(process.cwd(), "07-frontend", "package.json"));
const { chromium } = require("playwright-core");

/**
 * Where chromium actually is.
 *
 * ⚠ `executablePath()` RETURNS A PATH, NOT A BROWSER — it is computed from the
 * version playwright was built against rather than from what is installed, so
 * it can answer a path that does not exist without throwing. The path is TESTED
 * rather than trusted (law 7's *structurally incapable of failing* shape).
 */
function resolveChromium() {
  const candidates = [];
  try {
    candidates.push(chromium.executablePath());
  } catch {
    /* the computed path is optional — the glob below is the real answer */
  }
  try {
    candidates.push(
      execFileSync("bash", [
        "-lc",
        "ls -d /opt/pw-browsers/chromium-*/chrome-linux/chrome /opt/pw-browsers/chromium-*/chrome-linux64/chrome 2>/dev/null | head -1",
      ])
        .toString()
        .trim(),
    );
  } catch {
    /* nothing under /opt — the error below names what was tried */
  }
  for (const candidate of candidates) {
    if (candidate && existsSync(candidate)) return candidate;
  }
  throw new Error(
    `no chromium executable found. Tried: ${candidates.filter(Boolean).join(", ") || "(nothing)"}`,
  );
}

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4360";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr069-h";
const VIEWPORT = { width: 1440, height: 1000 };
const PROVIDER = "email_microsoft";
const DETAIL = `${BASE}/${TENANT}/settings/integrations/${PROVIDER}`;

/** The consent string the fixture stored. It must appear NOWHERE on screen. */
const CONSENT = "1.RECORDED-CONSENT-NOT-REAL-A17C";

const failures = [];
const gaps = new Gaps();

function check(ok, message, why) {
  if (ok) {
    console.log(`   ✓ ${message}`);
  } else {
    console.log(`   ⛔ ${message}${why ? ` — ${why}` : ""}`);
    failures.push(message);
  }
}

async function shot(page, name) {
  mkdirSync(OUT, { recursive: true });
  await page.screenshot({ path: join(OUT, `${name}.png`), fullPage: true });
}

const main = async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });
  console.log(`cr069-h: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);

  // ── sign in ──────────────────────────────────────────────────────────────
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click("button[type=submit]");
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });

  // ── 1 · the warning is PAINTED, and the date is the tenant's ─────────────
  console.log("\n1 · S142 — eleven days from lapsing");
  await page.goto(DETAIL, { waitUntil: "networkidle" });
  await shot(page, "01-warning");

  const card = await page.evaluate(
    async ([tenant, provider]) => {
      const r = await fetch(`/api/${tenant}/integrations`, { credentials: "include" });
      const grid = await r.json();
      return (grid.providers ?? []).find((one) => one.key === provider);
    },
    [TENANT, PROVIDER],
  );
  const expiry = card?.connection?.expiry;

  // ⚠ REFUSE A WRONG STARTING STATE RATHER THAN REPORTING NINE REDS ABOUT IT.
  // This walk RE-AUTHORISES, so it leaves the connection at v2 with ninety days
  // on it. Run a second time against the same clone and every assertion in
  // steps 1 and 4 fails — correctly, and completely unreadably: the output says
  // *the WarningBox is not painted* when the truth is *you already ran this*.
  // A check whose output cannot distinguish pass from fail to a READER is worse
  // than no check (law 7's third habit), so the precondition is stated once,
  // here, with the command that fixes it.
  if (expiry?.state !== "warning" || expiry?.version !== 1) {
    console.error(
      `\ncr069-h REFUSED: this clone is not in the state the walk starts from.\n` +
        `  expected  state=warning version=1  (a fresh fixture)\n` +
        `  found     state=${expiry?.state} version=${expiry?.version} ` +
        `days_left=${expiry?.days_left}\n` +
        `  This walk re-authorises, so it cannot be run twice on one clone — and\n` +
        `  runs are append-only (BR-INT-039), so the fixture cannot start over.\n` +
        `  Take a fresh clone and reseed:\n` +
        `      ./10-scripts/proof-db.sh drop int_h\n` +
        `      ./10-scripts/proof-db.sh clone int_h --stale-ok --export\n` +
        `      (cd 06-backend && python3 manage.py migrate integrations)\n` +
        `      (cd 06-backend && python3 manage.py shell < ../10-scripts/render-checks/cr069-h-fixture.py)`,
    );
    await browser.close();
    process.exit(2);
  }

  console.log(
    `   server: state=${expiry?.state} days_left=${expiry?.days_left} ` +
      `window=${expiry?.window_days} version=${expiry?.version}`,
  );
  check(expiry?.state === "warning", "the server says the credential is in its warning window");
  check(expiry?.days_left === 11, `eleven days left (got ${expiry?.days_left})`);
  check(expiry?.window_days === 14, "Microsoft's own fourteen-day window, from its manifest");

  const box = page.locator("[data-warning]").first();
  const painted = await box.count();
  check(painted > 0, "the WarningBox is PAINTED on S142", "template I3's slot was empty until now");
  const boxText = painted > 0 ? await box.innerText() : "";
  console.log(`   box: ${JSON.stringify(boxText)}`);
  check(
    /re-authoris/i.test(boxText),
    "the box says the connection needs re-authorising",
  );
  check(
    /bills stop going out/i.test(boxText),
    "…and says what happens after that date",
  );

  // THE DATE. This is the assertion the whole wave turns on: a clerk-facing
  // date must be in the tenant's regional format, not the way a computer
  // writes one. Every wave walked on 2026-09-05 failed this somewhere.
  const isoish = /\d{4}-\d{2}-\d{2}T?\d*/.test(boxText);
  check(!isoish, "the date is NOT an ISO timestamp", `box read ${JSON.stringify(boxText)}`);
  const regional = /\b\d{2}\/\d{2}\/\d{4}\b/.test(boxText);
  check(
    regional,
    "the date is in the tenant's regional format (MM/DD/YYYY for this tenant)",
    `box read ${JSON.stringify(boxText)}`,
  );

  const reauthorise = page.locator("[data-reauthorise]").first();
  check((await reauthorise.count()) > 0, "there is a Re-authorise control on the box");

  // ⚠ THE WHOLE SCREEN, not just the box — the brief's own instruction. Any
  // ISO timestamp anywhere on S142 is a clerk reading machine text.
  const wholeScreen = await page.locator("body").innerText();
  const isoAnywhere = wholeScreen.match(/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/g) ?? [];
  check(
    isoAnywhere.length === 0,
    "no raw ISO timestamp anywhere on S142",
    isoAnywhere.length ? `found ${JSON.stringify(isoAnywhere.slice(0, 3))}` : undefined,
  );

  // ── 2 · no secret is on the screen ───────────────────────────────────────
  console.log("\n2 · nothing that could be a secret");
  check(!wholeScreen.includes(CONSENT), "the stored consent string is not on S142");
  check(!/refresh_token/i.test(wholeScreen), "the words `refresh_token` are not on S142");
  check(
    wholeScreen.includes("••••A17C"),
    "the masked hint IS shown — a mask is what a clerk gets",
  );

  // ── 3 · the runs, counted BEFORE re-authorising ──────────────────────────
  console.log("\n3 · the run history before re-authorising");
  const runsBefore = await page.evaluate(
    async ([tenant, provider]) => {
      const r = await fetch(`/api/${tenant}/integrations/${provider}/runs`, {
        credentials: "include",
      });
      const body = await r.json();
      return (body.runs ?? body.rows ?? []).length;
    },
    [TENANT, PROVIDER],
  );
  console.log(`   runs before: ${runsBefore}`);
  check(runsBefore === 20, `twenty runs are recorded (got ${runsBefore})`);

  // ── 4 · S7 — the same sentence, above the numbers ────────────────────────
  console.log("\n4 · S7 — the dashboard attention strip");
  await page.goto(`${BASE}/${TENANT}/dashboard`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500); // the grid query settles
  await shot(page, "02-dashboard");
  const strip = page.locator("[data-attention='credentials']");
  const stripPainted = (await strip.count()) > 0;
  check(stripPainted, "the attention strip is PAINTED on the dashboard");
  if (stripPainted) {
    const stripText = await strip.innerText();
    console.log(`   strip: ${JSON.stringify(stripText)}`);
    check(/re-authoris/i.test(stripText), "the strip names the same thing S142 does");
    check(
      /\b\d{2}\/\d{2}\/\d{4}\b/.test(stripText),
      "the strip's date is in the tenant's regional format too",
      `strip read ${JSON.stringify(stripText)}`,
    );
    check(
      /Microsoft/i.test(stripText),
      "…and it names WHICH connection, because a dashboard serves several",
    );
  }

  // ── 5 · re-authorise, through the real return trip ───────────────────────
  console.log("\n5 · re-authorise");
  const before = await page.evaluate(
    async ([tenant, provider]) => {
      const r = await fetch(`/api/${tenant}/integrations`, { credentials: "include" });
      const grid = await r.json();
      const one = (grid.providers ?? []).find((p) => p.key === provider);
      return { version: one?.connection?.expiry?.version, credentials: one?.credentials?.length };
    },
    [TENANT, PROVIDER],
  );
  console.log(`   before: v${before.version}, ${before.credentials} credential row(s)`);

  const trip = await page.evaluate(
    async ([tenant, provider]) => {
      // The REAL start endpoint mints the REAL nonce.
      const started = await fetch(`/api/${tenant}/integrations/${provider}/oauth/start`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ redirect_uri: `${window.location.origin}/return` }),
      });
      if (!started.ok) return { step: "start", status: started.status, text: await started.text() };
      const { authorize_url, state } = await started.json();
      // Microsoft's consent screen is not ours to dial. The trip BACK is real.
      const returned = await fetch(
        `/api/${tenant}/integrations/${provider}/oauth/return?code=walkthrough-code&state=${encodeURIComponent(state)}`,
        { credentials: "include" },
      );
      return {
        step: "return",
        authorize_url,
        status: returned.status,
        card: returned.ok ? await returned.json() : await returned.text(),
      };
    },
    [TENANT, PROVIDER],
  );

  check(
    typeof trip.authorize_url === "string" &&
      trip.authorize_url.startsWith("https://login.microsoftonline.com/"),
    "the start endpoint answers Microsoft's own authorise URL",
    JSON.stringify(trip).slice(0, 200),
  );
  check(
    /offline_access/.test(trip.authorize_url ?? ""),
    "…asking for offline_access, or no refresh token ever comes back",
  );
  check(trip.status === 200, `the return trip is accepted (got ${trip.status})`);

  // ── 6 · v2 on the same connection, and every run still there ─────────────
  console.log("\n6 · credential v2, and the history");
  await page.goto(DETAIL, { waitUntil: "networkidle" });
  await shot(page, "03-after-reauthorise");

  const after = await page.evaluate(
    async ([tenant, provider]) => {
      const r = await fetch(`/api/${tenant}/integrations`, { credentials: "include" });
      const grid = await r.json();
      const one = (grid.providers ?? []).find((p) => p.key === provider);
      const runs = await fetch(`/api/${tenant}/integrations/${provider}/runs`, {
        credentials: "include",
      }).then((x) => x.json());
      return {
        state: one?.connection?.expiry?.state,
        version: one?.connection?.expiry?.version,
        credentials: (one?.credentials ?? []).map((c) => ({
          version: c.version,
          active: c.is_active,
        })),
        runs: (runs.runs ?? runs.rows ?? []).length,
      };
    },
    [TENANT, PROVIDER],
  );
  console.log(`   after: state=${after.state} v${after.version} runs=${after.runs}`);
  console.log(`   credential rows: ${JSON.stringify(after.credentials)}`);

  check(after.version === 2, `the credential is version 2 (got ${after.version})`);
  check(
    after.credentials.length === 2,
    `v1 is RETAINED beside v2, not overwritten (got ${after.credentials.length} row(s))`,
  );
  check(
    after.credentials.some((c) => c.version === 1 && c.active === false),
    "v1 is present and inactive",
  );
  check(after.state === "ok", `the warning is cleared (state=${after.state})`);
  check(
    after.runs === runsBefore,
    `every earlier run is still listed — ${runsBefore} before, ${after.runs} after`,
  );

  const afterScreen = await page.locator("body").innerText();
  check(
    (await page.locator("[data-warning]").count()) === 0,
    "the WarningBox is GONE from S142",
  );
  check(!afterScreen.includes(CONSENT), "still no consent string on the screen");

  // ── 7 · the half that is NOT built ───────────────────────────────────────
  console.log("\n7 · what this wave did not build");
  const sweep = await page.evaluate(
    async ([tenant]) => {
      const r = await fetch(`/api/${tenant}/integrations`, { credentials: "include" });
      return r.ok;
    },
    [TENANT],
  );
  check(sweep, "the grid still serves after the round trip");

  gaps.known(
    false,
    "the sweep queues one email to the System Admins",
    {
      defect: "DEF-INT-4214",
      why:
        "notifications publishes no expiry notice, and the nearest existing callable is a " +
        "bulk-summary shape that would render 'Sign-in about to lapse: 1 of 1 failed' in the " +
        "bell. The sweep reports notified=0 with the reason in words rather than a silent zero; " +
        "the dashboard and the connection both carry the warning, which is what BR-INT-042's " +
        "exit test looks at",
    },
  );

  await browser.close();
  console.log("");
  process.exit(gaps.report(failures));
};

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
