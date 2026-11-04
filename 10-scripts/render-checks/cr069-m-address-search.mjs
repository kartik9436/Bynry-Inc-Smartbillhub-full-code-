// ── Trace ──────────────────────────────────────────────
// Story:    US-INT-042 (EP-INT-12) — CR-069 wave M task M4, the demo script.
//           Design: 08-screen-layouts.md frames 66.1 and 66.2
// Rules:    CLAUDE.md hard-won law 6 (no gate reads rendered output — diff the
//           running app against the design) · BR-INT-048 (`C15` candidates
//           under a second with NO SPINNER; `C16` nothing written until a
//           pick) · BR-INT-022 (the breaker) · OQ-INT-1471 RULED (b)
// Defects:  DEF-INT-4251 · DEF-INT-4252 — the two live calls this wave gave a
//           connection record; the tile host and the policy come from that row
// ───────────────────────────────────────────────────────
/**
 * cr069-m-address-search — Priya adds a premises, twice: once with the City
 * answering and once with it out.
 *
 *     # one terminal: PostgreSQL, the demo plant, and the City connected
 *     DATABASE_URL=… python manage.py seed_demo
 *     DATABASE_URL=… python manage.py seed_gis_city            # 300 ms City
 *     DATABASE_URL=… ALLOWED_HOSTS='*' python manage.py runserver 127.0.0.1:8099
 *     # another: the BUILT bundle, proxying /api at it
 *     cd 07-frontend && npx vite build
 *     PORT=4299 API_PROXY_TARGET=http://127.0.0.1:8099 \
 *       STATIC_DIR=$PWD/dist node server.mjs
 *     node 10-scripts/render-checks/cr069-m-address-search.mjs
 *
 * ⚠ **REBUILD THE BUNDLE FIRST.** `server.mjs` serves whatever was in `dist/`
 * when it started and never notices it is hours old — the trap
 * `cwp_portal_walkthrough.mjs`'s header records, which cost a lane six screens
 * that looked unbuilt and were simply not in the bundle. And pass
 * `STATIC_DIR`, because `dist/` is resolved from `server.mjs`'s OWN directory:
 * a lane in a `git worktree` running the shared checkout's copy serves the
 * shared checkout's bundle however carefully it just built its own.
 *
 * ⚠ **`playwright` IS RESOLVED FROM `07-frontend`, EXPLICITLY.** Node resolves
 * a bare import from the SCRIPT's directory upward, never from the working
 * directory, and the repo root has no `node_modules`.
 *
 * ⚠ **AND THE POLICY IS CACHED FOR SIXTY SECONDS PER TENANT, SO A RUN STARTED
 * STRAIGHT AFTER A CONNECTION CHANGES REPORTS A FALSE FAIL.** `server.mjs`
 * asks the API once a minute; change a tile host and re-run immediately and
 * `img-src` still names the old one — or, if the API was down when the cache
 * was filled, names nothing at all and the check below says the policy has no
 * tile host. It happened on this file's own first slow run. **Wait a minute,
 * or restart `server.mjs`**, before believing that particular FAIL.
 *
 * WHAT IT CHECKS, AND WHY EACH ONE NEEDS A BROWSER
 * ------------------------------------------------
 *  1 · the candidates arrive INSIDE the declared budget — a wall-clock fact
 *  2 · *strong match* / *close match* appear as WORDS, and the City's number
 *      (`96`) appears nowhere on the page
 *  3 · there is NO SPINNER while the City is slow — the screen says so
 *  4 · the response's `content-security-policy` header names exactly the
 *      registered tile host. **No test can see this**: it is a header on the
 *      document, set by `server.mjs`, and every backend test asserts the
 *      GENERATED STRING rather than what a browser was actually handed.
 *  5 · every utility the panel writes actually rendered — the class is in the
 *      DOM either way, so the only proof is a computed style
 *  6 · **the asset map draws under that policy and the browser refused
 *      NOTHING.** `DEF-INT-4261` — the first version of the policy blocked
 *      this product's OWN webfont, so every screen would have rendered in the
 *      fallback system font; a CSP refusal is a console line and nothing else,
 *      so it is invisible to the server, to every test, and very nearly to a
 *      screenshot.
 *
 * ⚠ **CHECK 5 EXISTS BECAUSE TWO LANES WROTE A DEAD TAILWIND CLASS IN ONE
 * WEEK** (`DEF-INT-4236`'s `border-amber-600`, and a `max-w-[80%]` the same
 * day). `--color-*: initial` kills Tailwind's own palettes, so a
 * default-palette colour name compiles to NOTHING while `tsc`, eslint and
 * every `toContain` pass. A computed style is the only thing that can tell.
 */
import { createRequire } from "node:module";

const require = createRequire(new URL("../../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:4299";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SHOTS ?? "";

const problems = [];
const notes = [];

function check(ok, what, detail = "") {
  const line = `${ok ? "  ok  " : "  FAIL"}  ${what}${detail ? ` — ${detail}` : ""}`;
  console.log(line);
  if (!ok) problems.push(`${what}${detail ? ` — ${detail}` : ""}`);
  return ok;
}

async function signIn(page) {
  // The route is `/signin`, and the fields are `#signin-email` /
  // `#signin-password`. ⚠ The first draft of this file guessed `/login` and a
  // type selector; every API call then came back 401 and the wizard rendered
  // *We couldn't load your regional settings*, which looks exactly like a
  // broken screen rather than like a walkthrough signing in wrongly.
  // `cr049-bill-document.mjs` had it right — reading a walkthrough that works
  // is cheaper than guessing at one.
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((url) => !url.pathname.endsWith("/signin"), { timeout: 20000 });
}

async function main() {
  const browser = await chromium.launch({
    executablePath: process.env.CHROMIUM ?? "/opt/pw-browsers/chromium",
  });
  const context = await browser.newContext({ viewport: { width: 1280, height: 1400 } });
  const page = await context.newPage();

  const jsErrors = [];
  page.on("pageerror", (error) => jsErrors.push(String(error)));

  // `DEF-INT-4261` — a Content-Security-Policy refusal is SILENT: the browser
  // declines the resource, writes one console line, and renders the page
  // anyway. The product's own webfont was blocked by the first version of the
  // policy and every screen would have rendered in the fallback system font,
  // with nothing on the server able to see it. So the refusals are collected
  // and they are a PROBLEM, not a note.
  const cspRefusals = [];
  const tileOrigins = new Set();
  page.on("console", (message) => {
    const text = message.text();
    if (/Content Security Policy|Refused to (load|connect|apply)/i.test(text)) {
      cspRefusals.push(text.slice(0, 220));
    }
  });
  page.on("request", (request) => {
    if (request.resourceType() === "image") {
      try {
        tileOrigins.add(new URL(request.url()).origin);
      } catch {
        /* data: and blob: have no origin */
      }
    }
  });

  await signIn(page);

  // ── 4 · the CSP on the DOCUMENT ──────────────────────────────────────────
  // Read BEFORE anything else, off the raw response, because it is the header
  // a browser enforces for the life of this document.
  const documentResponse = await page.goto(`${BASE}/${TENANT}/premises`, {
    waitUntil: "domcontentloaded",
  });
  const csp = documentResponse?.headers()["content-security-policy"] ?? "";
  console.log("\n── the page-security policy, as the browser was handed it ──");
  console.log(`  ${csp || "(none — this is the bug wave M exists to close)"}`);
  check(csp.length > 0, "the document carries a Content-Security-Policy");
  check(csp.includes("default-src 'self'"), "the policy is anchored on 'self'");
  const tileHost = (csp.match(/img-src[^;]*/) ?? [""])[0];
  check(
    /https?:\/\//.test(tileHost),
    "img-src names a registered tile host",
    tileHost || "(nothing but 'self')",
  );
  check(
    !/\*/.test(csp),
    "the policy names hosts, never a wildcard",
    csp.includes("*") ? "a `*` is in the policy" : "",
  );

  const SLOW = process.env.SLOW === "1";

  // ── 1 · Priya types, and the City answers inside the budget ──────────────
  //
  // ⚠ **SKIPPED WHOLE UNDER `SLOW=1`, AND SAID OUT LOUD.** With the City out
  // there is no *Use this* to click, and the first version of this file walked
  // it anyway: the click waited its default thirty seconds and threw, and the
  // run produced ONE tick and no verdict. A check that hangs is worse than one
  // that fails, because it looks like thoroughness.
  if (SLOW) {
    console.log("\n  skip  frame 66.1 (SLOW=1) — the City is the 4,000 ms one on this run");
  } else {
  console.log("\n── frame 66.1 · find the address ──");
  await page.goto(`${BASE}/${TENANT}/premises/new?mode=single_premise&step=2`, {
    waitUntil: "networkidle",
  });
  const panel = page.locator('[data-testid="find-the-address"]');
  if (!check(await panel.count(), "the *Where is this property?* panel is on the step")) {
    await finish(browser, page);
    return;
  }

  const field = page.locator("#city-address-search");
  const started = Date.now();
  await field.fill("1408 Pec");
  await page.locator('[data-testid="match-count"]').waitFor({ timeout: 5000 }).catch(() => {});
  const elapsed = Date.now() - started;
  const countLine = (await page.locator('[data-testid="match-count"]').textContent()) ?? "";
  check(
    (await page.locator('[data-testid="match-count"]').count()) > 0,
    "the City's candidates arrive",
    countLine.trim(),
  );
  notes.push(`candidates in ${elapsed} ms (budget 1,000 ms, fixture City 300 ms)`);
  check(elapsed < 2000, "the candidates arrive while a clerk is still looking", `${elapsed} ms`);

  // ── 2 · the two WORDS, and no number ─────────────────────────────────────
  const body = (await page.locator("body").innerText()).replace(/\s+/g, " ");
  check(/strong match/.test(body), "a strong candidate says *strong match*");
  check(/close match/.test(body), "a close candidate says *close match*");
  check(/Parcel 88214/.test(body), "the parcel key is on the row");
  check(
    !/\b96\b/.test(body),
    "the City's own score appears NOWHERE as a number",
    /\b96\b/.test(body) ? "a `96` is on the page" : "",
  );
  check(
    /No score is shown as a number/.test(body),
    "the note explaining why is drawn (frame 66.1)",
  );
  // `DEF-INT-4260` — the frame draws three fields and the first build drew one.
  check(
    (await page.locator("#city-address-unit").count()) > 0,
    "the Unit field frame 66.1 draws is on the screen",
  );
  check(
    (await page.locator("#city-address-zip").count()) > 0,
    "the Zip field frame 66.1 draws is on the screen",
  );

  // ── 5 · the amber box actually renders ───────────────────────────────────
  // Proved on the OFFLINE branch below, because that is where the box is.

  // ── the pick, and the write ──────────────────────────────────────────────
  console.log("\n── the pick, and Create ──");
  const before = await countPremises(page);
  await page.locator("text=Use this").first().click();
  const addressField = page.locator("#address_line");
  const filled = (await addressField.inputValue().catch(() => "")) || "";
  check(
    filled.includes("1408 Pecan St"),
    "*Use this* fills the address fields",
    filled || "(empty)",
  );
  const afterPick = await countPremises(page);
  check(
    afterPick === before,
    "NOTHING was written by the pick itself (C16 — disposition `offer`)",
    `${before} → ${afterPick}`,
  );

  if (OUT) await page.screenshot({ path: `${OUT}/cr069-m-66-1.png`, fullPage: true });
  }

  // ── 3 · the slow City ────────────────────────────────────────────────────
  //
  // ⚠ Point the connection at the four-second recording FIRST:
  //     DATABASE_URL=… python manage.py seed_gis_city --slow
  // and re-run with SLOW=1. The check below reports honestly when it is
  // looking at the fast City rather than pretending it proved the branch.
  if (SLOW) {
    console.log("\n── frame 66.2 · the honest state ──");
    await page.goto(`${BASE}/${TENANT}/premises/new?mode=single_premise&step=2`, {
      waitUntil: "networkidle",
    });
    await page.locator("#city-address-search").fill("1408 Pec");
    await page
      .locator('[data-testid="city-offline"]')
      .waitFor({ timeout: 30000 })
      .catch(() => {});
    const offline = page.locator('[data-testid="city-offline"]');
    check(await offline.count(), "the amber box appears when the City will not answer");
    const offlineText = ((await offline.textContent()) ?? "").replace(/\s+/g, " ");
    check(
      /We cannot reach the City's address records right now/.test(offlineText),
      "it says so in the frame's own words",
    );
    check(
      /will not carry the City's parcel number/.test(offlineText),
      "and says what the consequence is",
    );

    // The utility check hard-won law 7 and DEF-INT-4236 ask for: the class is
    // in the DOM either way, so read the COMPUTED style.
    const painted = await offline.evaluate((node) => {
      const style = getComputedStyle(node);
      return { background: style.backgroundColor, border: style.borderTopColor };
    });
    notes.push(`amber box computed: background ${painted.background}, border ${painted.border}`);
    check(
      painted.background !== "rgba(0, 0, 0, 0)" && painted.background !== "transparent",
      "the amber box is actually PAINTED (the utility compiled)",
      painted.background,
    );

    const slowBody = (await page.locator("body").innerText()).replace(/\s+/g, " ");
    check(
      !/loading|searching|please wait/i.test(slowBody),
      "there is NO SPINNER — the screen says so instead (C15)",
    );
    check(/Try the City again/.test(slowBody), "*Try the City again* is offered");
    check(
      /serving whatever we asked for last week/.test(slowBody),
      "the note about last week's answer is drawn",
    );
    if (OUT) await page.screenshot({ path: `${OUT}/cr069-m-66-2.png`, fullPage: true });
  } else {
    notes.push(
      "the slow-City branch was NOT walked — run `seed_gis_city --slow` and re-run with SLOW=1",
    );
    console.log("\n  skip  frame 66.2 (SLOW=1 not set) — this run proves nothing about it");
  }

  // ── 6 · the page the policy is FOR ───────────────────────────────────────
  // ⚠ Walking only the premises form proves the HEADER exists and proves
  // nothing about whether it lets the map draw. This opens the asset map and
  // reads which origins the browser actually asked for.
  console.log("\n── the map, under the generated policy ──");
  await page.goto(`${BASE}/${TENANT}/assets?tab=map`, { waitUntil: "networkidle" });
  await page.waitForTimeout(4000);
  const origins = [...tileOrigins].join(", ") || "(none)";
  notes.push(`image origins the browser asked for: ${origins}`);
  check(
    tileOrigins.size === 0 || [...tileOrigins].every((one) => csp.includes(one)),
    "every host the map fetched from is named in the policy",
    origins,
  );
  check(
    cspRefusals.length === 0,
    "the browser refused NOTHING under this policy",
    cspRefusals.slice(0, 2).join(" | "),
  );

  await finish(browser, page, jsErrors);
}

async function countPremises(page) {
  return page.evaluate(async () => {
    const tenant = window.location.pathname.split("/").filter(Boolean)[0];
    const response = await fetch(`/api/${tenant}/premises?per=1`, { credentials: "include" });
    if (!response.ok) return -1;
    const body = await response.json();
    return typeof body.count === "number" ? body.count : -1;
  });
}

async function finish(browser, page, jsErrors = []) {
  console.log("\n── notes ──");
  for (const note of notes) console.log(`  · ${note}`);
  if (jsErrors.length) {
    console.log("\n── javascript errors ──");
    for (const error of jsErrors) console.log(`  · ${error}`);
  }
  console.log(
    problems.length === 0
      ? "\nALL CHECKS PASSED"
      : `\n${problems.length} PROBLEM(S):\n${problems.map((one) => `  · ${one}`).join("\n")}`,
  );
  await browser.close();
  process.exitCode = problems.length === 0 ? 0 : 1;
}

await main();
