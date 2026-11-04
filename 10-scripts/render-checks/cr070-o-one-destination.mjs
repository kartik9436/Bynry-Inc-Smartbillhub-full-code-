/**
 * RENDERED-OUTPUT CHECK — CR-070 wave O, "one destination", in a real browser.
 *
 * ⚠ **WHY THIS EXISTS, AND WHY IT IS THE ONLY THING THAT COULD FIND WHAT IT
 * FINDS.** Hard-won law 6: no gate in this repository looks at rendered output.
 * Wave O DELETES a screen and REPOINTS five links, and **a link that silently
 * goes nowhere passes every test in this repo** — `tsc` is happy, eslint is
 * happy, and every assertion that a link EXISTS still passes while the reader
 * lands on a blank frame. `G93` catches the retired path being written back;
 * only a browser catches the new one being wrong.
 *
 * ⚠ **IT RE-RUNS `cr070-b`'s EIGHT ACTS THROUGH THE NEW DOOR RATHER THAN
 * REPLACING THEM.** `cr070-b-fourteen-doors-and-the-queue.mjs` still stands and
 * still proves phase 0's launch claim; what changed is the SCREEN those acts
 * are pressed from, so the same behaviours are re-asserted on the premises.
 * ⚠ **EIGHT, and the execution plan said seven in four places (`DEF-WRK-3748`)**
 * — `CR-070 §W.6`, `ConnectionAct` and `cr070-b` all say eight, and the eighth
 * is *Raise order*.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   # 1 · a private, seeded database (10-scripts/proof-db.sh, read it first)
 *   eval "$(10-scripts/proof-db.sh clone cr070o --export)"
 *   export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false
 *
 *   # 2 · the product
 *   (cd 06-backend && python manage.py runserver 127.0.0.1:8073 --noreload &)
 *   (cd 07-frontend && ./node_modules/.bin/vite build &&
 *      PORT=4273 API_PROXY_TARGET=http://127.0.0.1:8073 node server.mjs &)
 *
 *   # 3 · this
 *   SMOKE_BASE=http://127.0.0.1:4273 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr070-o-one-destination.mjs
 *
 * ⚠ **NO FIXTURE STEP, AND THAT IS A DIFFERENCE FROM `cr070-b`.** This
 * walkthrough needs only the seeded estate: a build, its premises, and an
 * account. It HOLDS and RELEASES the build — which it puts back — and it raises
 * nothing and accepts nothing, so it is re-runnable without re-seeding. A
 * walkthrough that cannot be re-run is a walkthrough nobody re-runs.
 *
 * ── WHAT IT ASSERTS (demo script O, clicked) ──────────────────────────────
 *   1  **THE BUILD IS ON THE PREMISES** (demo step 1). Premises → the build's
 *      own address → a **Build** tab that was not there yesterday, carrying the
 *      state, how it is done, the target, the charges at TWO decimals, the
 *      progress fraction and the unit count.
 *   2  **THE EIGHT ACTS ARE THERE, EACH ENABLED OR REFUSED IN WORDS**
 *      (`BR-SHL-025`), Cancel alone on the danger tier, and the tier's colour
 *      read from COMPUTED STYLE — B14 rule 21 means a utility that did not
 *      compile renders as nothing while `data-variant="danger"` is still in the
 *      DOM.
 *   3  **HOLD IS A ROUND TRIP THROUGH THE SERVER** (demo steps 2–3): the state
 *      comes back from `GET /premises/{id}/build`, not patched on the screen.
 *      Release puts it back and the pair swap.
 *   4  **THE SERVER REFUSES, NOT THE SCREEN** — the half a disabled button
 *      cannot prove, called from the page's own session.
 *   5  **A PREMISES WITH NO BUILD RENDERS NO BUILD TAB AT ALL** (law 2, `G13`).
 *      The one thing on this screen that is proved by an ABSENCE, so it is
 *      checked on a second address rather than assumed.
 *   6  **THE WORK ORDERS TAB** (demo step 4) lists the jobs at the address with
 *      what each stands on.
 *   7  **THE ACCOUNT HAS TWELVE TABS AND THE TWELFTH IS WORK** (demo step 5).
 *   8  **A BOOKMARKED `/connections/<uuid>` LANDS ON THE PREMISES** (demo step
 *      6) — the URL is typed in, and the address bar is read afterwards.
 *   9  **NO ANCHOR ANYWHERE GOES TO `/connections/<id>`** (demo step 7) — read
 *      off the DOM of the two hosts and of the approval queue, which is the
 *      rendered half of `G93`.
 *  10  **NO DATABASE ID AND NO INTERNAL CODE REACHES THE CLERK** (B14 rules 31
 *      and 32), on both hosts.
 *  11  **NO SIDEWAYS SCROLL AT 1440.**
 *   Screenshots land in `$SMOKE_OUT` (default /tmp/cr070-o-destination), beside
 *   which a reviewer opens `wireframes/Work-002.png`.
 *
 * ── WHAT IT DOES *NOT* ASSERT, AND WHY ────────────────────────────────────
 * **The isolation step is not here.** Lone Star Ridge is not seeded, and
 * provisioning a second utility inside a browser walkthrough would make this
 * file a seeder. The wall is proved where it can be proved properly —
 * `06-backend/tests/test_us_wrk_002_one_destination.py` asserts that a Lone
 * Star Ridge session sees `{"build": null}` and a zero-row list for a Brazos
 * Bend premises. Stated here rather than quietly skipped.
 */

import { execFileSync } from "node:child_process";
import { mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const require = createRequire(join(process.cwd(), "07-frontend", "package.json"));
const { chromium } = require("playwright-core");

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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4273";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr070-o-destination";
const VIEWPORT = { width: 1440, height: 1000 };

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

const SIDEWAYS =
  "Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)";

/** The eight acts of `Work-002`'s row, in the order the screen draws them. */
const ACTS = [
  "hold",
  "release",
  "cancel",
  "waitingOn",
  "addService",
  "markOutstanding",
  "closeOutstanding",
  "raiseOrder",
];

/** Anything a clerk must never be shown (B14 rules 31 and 32). */
const FORBIDDEN_IN_CLERK_COPY = [
  [/\bBR-[A-Z]{3}-\d{3,5}\b/, "a business-rule id"],
  [/\bOQ-(?:[A-Z]{3}-)?\d{3,5}\b/, "an open-question id"],
  [/\bDEF-(?:[A-Z]{3}-)?\d{3,5}\b/, "a defect id"],
  [/\bUS-[A-Z]{3}-\d{3,5}\b/, "a story id"],
  [/\bWork-0\d\d\b/, "a Work-nnn screen number"],
  [/\bCR-0\d\d\b/, "a change-request id"],
  [/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/, "a database id"],
  // ⚠ **ADDED AFTER THIS WALKTHROUGH'S FIRST RUN FOUND IT (`DEF-WRK-3752`).**
  // Two tab labels rendered as `metering.premises.tab.build` and
  // `customers.account.tab.work` — the RAW CATALOGUE KEY, on a clerk's screen,
  // which B14 rule 32 forbids in as many words. `tsc`, eslint, every unit test
  // and **`G15` itself** all passed: the eleven catalogues agreed with each
  // other, because all eleven had lost the same keys. Nothing but a browser
  // could see it, which is hard-won law 6 in one line.
  [/\b[a-z][a-zA-Z]*(?:\.[a-z][a-zA-Z-]*){2,}\b/, "a raw catalogue key"],
];

async function signIn(page, tenant, email, password) {
  await page.goto(`${BASE}/${tenant}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", email);
  await page.fill("#signin-password", password);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });
}

/**
 * Call the API from INSIDE the page, so the request carries exactly the session
 * the screen has. A `fetch` from Node would need the cookie copied out and
 * would then be proving something about a different caller.
 */
async function api(page, method, path, body) {
  return page.evaluate(
    async ([m, p, b]) => {
      const response = await fetch(p, {
        method: m,
        headers: b === null ? {} : { "content-type": "application/json" },
        body: b === null ? undefined : JSON.stringify(b),
        credentials: "same-origin",
      });
      let payload = null;
      try {
        payload = JSON.parse(await response.text());
      } catch {
        payload = null;
      }
      return { status: response.status, body: payload };
    },
    [method, `/api/${TENANT}${path}`, body ?? null],
  );
}

async function readActs(page) {
  return page.evaluate(() =>
    [...document.querySelectorAll("[data-build-actions] button[data-act]")].map((b) => ({
      act: b.getAttribute("data-act"),
      label: (b.textContent ?? "").trim(),
      disabled: b.disabled,
      reason: b.getAttribute("data-blocked-reason"),
      variant: b.getAttribute("data-variant"),
      colour: getComputedStyle(b).color,
    })),
  );
}

/** Every anchor on the page, so a retired destination cannot hide in one. */
async function readHrefs(page) {
  return page.evaluate(() => [...document.querySelectorAll("a[href]")].map((a) => a.getAttribute("href")));
}

function words(sentence) {
  return sentence.replace(/[.…]+$/u, "").trim().split(/\s+/u).length;
}

async function tabIds(page) {
  return page.evaluate(() =>
    [...document.querySelectorAll('[role="tab"], .page-header-tabs button, [data-tab-id]')].map(
      (el) => (el.textContent ?? "").trim(),
    ),
  );
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });

  console.log(`cr070-o: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);
  await signIn(page, TENANT, EMAIL, PASSWORD);
  console.log("   signed in");

  // The build, found by ASKING the product rather than by a hardcoded id — the
  // seeded estate's numbers move and a walkthrough pinned to one is a
  // walkthrough that breaks for a reason that is not the product's.
  const list = await api(page, "GET", "/connections?per=200");
  const builds = list.body?.results ?? [];
  if (builds.length === 0) {
    console.log("⛔ this database has no builds — seed it and re-run.");
    process.exit(2);
  }
  const build = builds[0];
  const buildId = build.id;
  const premisesId = build.premises?.id ?? build.home?.id;
  console.log(`   the build under test: ${build.connection_no} at ${build.premises?.address}`);

  // ⚠ THE ROW ITSELF NOW CARRIES WHERE IT IS REACHED. Asserted here because it
  // is what every repointed link is built on: if `home` is absent, five links
  // fall back to plain text and nothing else in the product notices.
  check(
    build.home?.kind === "premises" || build.home?.kind === "account",
    `the list row says where the build lives — ${JSON.stringify(build.home)}`,
  );

  const buildPath = `/${TENANT}/premises/${premisesId}?tab=build`;

  // ═════════════════════════════════════════════════════════════════════════
  // 1 · THE BUILD IS ON THE PREMISES (demo step 1)
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── Premises → the build (demo step 1) ──");
  await page.goto(`${BASE}${buildPath}`, { waitUntil: "networkidle" });
  await page.waitForSelector("[data-build-tab]", { timeout: 20000 });
  await page.screenshot({ path: join(OUT, "01-premises-build-tab.png"), fullPage: true });

  const served = await api(page, "GET", `/premises/${premisesId}/build`);
  const facts = served.body?.build ?? null;
  check(facts !== null, "the premises serves a build");
  const buildText = (await page.textContent("[data-build-tab]")) ?? "";
  check(
    (await page.locator("[data-build-head]").count()) === 1,
    "the head is drawn exactly once",
  );
  check(
    (await page.locator(`[data-orders="${facts?.orders.done}/${facts?.orders.total}"]`).count()) === 1,
    `the progress fraction is the SERVER's — ${facts?.orders.done}/${facts?.orders.total}`,
  );
  check(
    (await page.locator(`[data-build-units="${facts?.units}"]`).count()) === 1,
    `the unit count is the SERVER's — ${facts?.units}`,
  );
  // CLAUDE.md hard rule 2 — DISPLAY two, and the server did the rounding. The
  // stored four-decimal value must not be on the screen.
  if (facts?.quote_total?.display) {
    check(
      buildText.includes(facts.quote_total.display),
      `the charge shows the server's two decimals — ${facts.quote_total.display}`,
    );
    check(
      !buildText.includes(facts.quote_total.stored),
      "…and the stored four-decimal value is nowhere on the screen",
    );
  }

  // ═════════════════════════════════════════════════════════════════════════
  // 2 · THE EIGHT ACTS, EACH ENABLED OR REFUSED IN WORDS
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── Work-002's action row, on its new host (demo step 1) ──");
  const acts = await readActs(page);
  check(acts.length === 8, `eight acts are on the screen (found ${acts.length})`);
  for (const want of ACTS) {
    const got = acts.find((a) => a.act === want);
    check(got !== undefined, `  ${want} is mounted`);
    if (!got) continue;
    const stated = got.disabled ? (got.reason ?? "").trim() !== "" : true;
    check(stated, `  ${want} is ${got.disabled ? `refused — "${got.reason}"` : "available"}`);
    if (got.disabled && got.reason) {
      check(words(got.reason) <= 6, `  …and that reason is ${words(got.reason)} words`);
    }
  }
  const danger = acts.filter((a) => a.variant === "danger");
  check(danger.length === 1 && danger[0].act === "cancel", "Cancel alone takes the danger tier");
  const dangerColour = danger[0]?.colour ?? "";
  const holdColour = acts.find((a) => a.act === "hold")?.colour ?? "";
  check(
    /^rgba?\(/.test(dangerColour) && dangerColour !== holdColour,
    `the danger tier actually painted: Cancel is ${dangerColour}, Hold is ${holdColour}`,
  );

  // ═════════════════════════════════════════════════════════════════════════
  // 3 · HOLD, WITH A REASON — AND THE STATE COMES BACK FROM THE SERVER
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── Hold… then Release… (demo steps 2–3) ──");
  const REASON = "Waiting on the tap permit";
  await page.click('button[data-act="hold"]');
  await page.waitForSelector("[data-act-prompt='hold']", { timeout: 10000 });
  await page.fill("#connection-act-text", REASON);
  await page.click("[data-act-confirm='hold']");
  await page.waitForFunction(
    () => /on hold/i.test(document.querySelector("[data-build-tab]")?.textContent ?? ""),
    { timeout: 20000 },
  );
  await page.screenshot({ path: join(OUT, "02-held.png"), fullPage: true });

  const afterHold = await api(page, "GET", `/premises/${premisesId}/build`);
  check(afterHold.body?.build?.state === "on_hold", "the server says the build is on_hold");
  check(
    ((await page.textContent("[data-waiting-on]")) ?? "").includes(REASON),
    `WAITING ON carries the typed reason — "${REASON}"`,
  );
  const heldActs = await readActs(page);
  check(
    heldActs.find((a) => a.act === "hold")?.disabled === true,
    `Hold is now refused — "${heldActs.find((a) => a.act === "hold")?.reason}"`,
  );
  check(
    heldActs.find((a) => a.act === "release")?.disabled === false,
    "…and Release is now the available one",
  );

  await page.click('button[data-act="release"]');
  await page.waitForFunction(
    () => !/on hold/i.test(document.querySelector("[data-build-tab]")?.textContent ?? ""),
    { timeout: 20000 },
  );
  const afterRelease = await api(page, "GET", `/premises/${premisesId}/build`);
  check(
    afterRelease.body?.build?.state !== "on_hold",
    `Release put it back — now ${afterRelease.body?.build?.state}`,
  );
  await page.screenshot({ path: join(OUT, "03-released.png"), fullPage: true });

  // ═════════════════════════════════════════════════════════════════════════
  // 4 · THE SERVER REFUSES — the half a disabled button cannot prove
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── the server's own refusal, not the screen's (BR-SHL-025) ──");
  const doubleRelease = await api(page, "POST", `/connections/${buildId}/release`, {});
  check(
    doubleRelease.status >= 400,
    `releasing a build that is not held is refused by the SERVER — HTTP ${doubleRelease.status}`,
  );
  const refusalKey = doubleRelease.body?.message_key ?? doubleRelease.body?.code ?? "";
  check(String(refusalKey).length > 0, `…with a catalogue key — ${JSON.stringify(refusalKey)}`);

  // ═════════════════════════════════════════════════════════════════════════
  // 5 · A PREMISES WITH NO BUILD RENDERS NO BUILD TAB AT ALL
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── the tab that is ABSENT, not empty (law 2, G13) ──");
  const premisesList = await api(page, "GET", "/premises?per=200");
  const withBuild = new Set(builds.map((b) => b.premises?.id));
  const bare = (premisesList.body?.results ?? []).find((p) => !withBuild.has(p.id));
  if (bare === undefined) {
    console.log("   (every seeded premises has a build — skipped, and SAID so)");
  } else {
    await page.goto(`${BASE}/${TENANT}/premises/${bare.id}`, { waitUntil: "networkidle" });
    await page.waitForSelector(".page-header", { timeout: 20000 });
    const tabs = await tabIds(page);
    check(
      !tabs.some((label) => /^build$/i.test(label)),
      `a premises with no build offers no Build tab — tabs are ${JSON.stringify(tabs)}`,
    );
    check(
      tabs.some((label) => /work orders/i.test(label)),
      "…and Work orders is still offered, because a job needs no build",
    );
    await page.screenshot({ path: join(OUT, "04-no-build-no-tab.png"), fullPage: true });
  }

  // ═════════════════════════════════════════════════════════════════════════
  // 6 · THE WORK ORDERS TAB (demo step 4)
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── Premises → Work orders (demo step 4) ──");
  await page.goto(`${BASE}/${TENANT}/premises/${premisesId}?tab=work-orders`, {
    waitUntil: "networkidle",
  });
  await page.waitForSelector("[data-work-orders-tab]", { timeout: 20000 });
  await page.screenshot({ path: join(OUT, "05-premises-work-orders.png"), fullPage: true });
  const servedOrders = await api(page, "GET", `/premises/${premisesId}/work-orders?per=200`);
  const orderRows = servedOrders.body?.results ?? [];
  const ordersText = (await page.textContent("[data-work-orders-tab]")) ?? "";
  if (orderRows.length === 0) {
    check(
      (await page.locator("[data-orders-empty]").count()) === 1,
      "an address with no jobs SAYS so rather than drawing an empty table (B14 rule 17)",
    );
  } else {
    check(
      ordersText.includes(orderRows[0].order_no ?? ""),
      `the jobs at this address are listed — ${orderRows.length}, first ${orderRows[0].order_no}`,
    );
    check(
      (await page.locator("[data-stands-on]").count()) === orderRows.length,
      "…and every row says which anchor it stands on",
    );
    // B14 rule 32 — the token travels, the SENTENCE is drawn.
    const tokens = await page.evaluate(() =>
      [...document.querySelectorAll("[data-stands-on]")].map((td) => ({
        token: td.getAttribute("data-stands-on"),
        text: (td.textContent ?? "").trim(),
      })),
    );
    check(
      tokens.every((t) => t.text !== t.token),
      `…in words rather than in the token — e.g. ${JSON.stringify(tokens[0])}`,
    );
  }

  // ═════════════════════════════════════════════════════════════════════════
  // 7 · THE ACCOUNT'S TWELFTH TAB (demo step 5)
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── Accounts → an account → Work (demo step 5) ──");
  const accounts = await api(page, "GET", "/accounts?per=5");
  const account = (accounts.body?.results ?? [])[0];
  check(account !== undefined, "this utility has an account to look at");
  if (account) {
    await page.goto(`${BASE}/${TENANT}/accounts/${account.id}?tab=work`, {
      waitUntil: "networkidle",
    });
    await page.waitForSelector("[data-work-orders-tab]", { timeout: 20000 });
    await page.screenshot({ path: join(OUT, "06-account-work-tab.png"), fullPage: true });
    const tabs = await tabIds(page);
    check(tabs.length === 12, `the account has twelve tabs (found ${tabs.length})`);
    check(
      tabs.some((label) => /^work$/i.test(label)),
      `…and the twelfth is Work — ${JSON.stringify(tabs)}`,
    );
  }

  // ═════════════════════════════════════════════════════════════════════════
  // 8 · A BOOKMARKED /connections/<uuid> LANDS ON THE PREMISES (demo step 6)
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── the old link, pasted in (demo step 6) ──");
  await page.goto(`${BASE}/${TENANT}/connections/${buildId}`, { waitUntil: "networkidle" });
  await page.waitForSelector("[data-build-tab], [data-build-redirect-failed]", { timeout: 20000 });
  const landed = new URL(page.url());
  check(
    landed.pathname.includes("/premises/") || landed.pathname.includes("/accounts/"),
    `a bookmarked build link lands on the build's home — ${landed.pathname}${landed.search}`,
  );
  check(
    !landed.pathname.includes("/connections/"),
    "…and the retired address is not where the reader ends up",
  );
  check(
    (await page.locator("[data-build-tab]").count()) === 1,
    "…on the very Build tab step 1 opened",
  );
  await page.screenshot({ path: join(OUT, "07-bookmark-redirect.png"), fullPage: true });

  // ═════════════════════════════════════════════════════════════════════════
  // 9–11 · No link back to the retired destination · no ids · no sideways
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── nothing points at the retired screen (demo step 7) ──");
  const surfaces = [
    ["the premises Build tab", `/${TENANT}/premises/${premisesId}?tab=build`],
    ["the premises Work orders tab", `/${TENANT}/premises/${premisesId}?tab=work-orders`],
    ["the approval queue", `/${TENANT}/work/awaiting-approval`],
    ["the Work orders list", `/${TENANT}/work/orders`],
    ["the New connects tab", `/${TENANT}/accounts?tab=new-connects`],
  ];
  for (const [label, path] of surfaces) {
    await page.goto(`${BASE}${path}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(500);
    const hrefs = await readHrefs(page);
    // `/connections/new` is the WIZARD and stays. Anything else after
    // `/connections/` is the retired destination.
    const offenders = hrefs.filter((h) => /\/connections\/(?!new$)./.test(h ?? ""));
    check(offenders.length === 0, `${label}: no link goes to the retired build screen`);
    if (offenders.length > 0) console.log(`      ${JSON.stringify(offenders.slice(0, 5))}`);

    const body = (await page.textContent("body")) ?? "";
    for (const [pattern, what] of FORBIDDEN_IN_CLERK_COPY) {
      const hit = body.match(pattern);
      check(hit === null, `${label}: no ${what} reaches the clerk${hit ? ` — "${hit[0]}"` : ""}`);
    }
    const sideways = await page.evaluate((expr) => eval(expr), SIDEWAYS);
    check(sideways === 0, `${label}: no sideways scroll at ${VIEWPORT.width} (${sideways}px)`);
  }

  await browser.close();
  console.log(`\nscreenshots → ${OUT}`);
  if (failures.length > 0) {
    console.log(`\n⛔ ${failures.length} failure(s):`);
    for (const f of failures) console.log(`   - ${f}`);
    process.exit(1);
  }
  console.log("\n✓ one destination: the build is on the premises and on the account, and the old link still works.");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
