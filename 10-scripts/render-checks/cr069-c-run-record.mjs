/**
 * RENDERED-OUTPUT CHECK — CR-069 wave C, *the run record and the word for not
 * knowing*, in a real browser.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: no gate in this repository looks at
 * rendered output. PO ruling 2026-09-03: *"ensure you do web walkthorugh before
 * you sign off the user story or build"*. A story is not signed off until this
 * has run green against a running product, on the wireframe pack's frames
 * (25.2 the mailbox's run rows · 51.1 a partial send opened · 51.2 the run
 * nobody designs for · 52.2 their words underneath ours), not r10.
 *
 * ⚠ **AND IT READS A COLOUR, ON PURPOSE (DEF-INT-3621).** This product's
 * Tailwind theme clears the stock palette (`--color-*: initial`), so
 * `text-amber-600` is a class no stylesheet declares: it is in the DOM, every
 * `toContain` assertion passes on it, and it renders NOTHING. Step 6 below
 * reads `color` on the 1 July run's result cell as COMPUTED STYLE and requires
 * the theme's amber — the one check that goes red when a token is fake, and
 * the one that proves *Unconfirmed* is visibly not green.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   eval "$(10-scripts/proof-db.sh clone cr069c --export)"   # sub-second
 *   DJANGO_SETTINGS_MODULE=config.settings.local \
 *     python3 06-backend/manage.py migrate integrations      # 0003, the items column
 *   DJANGO_SETTINGS_MODULE=config.settings.local \
 *     python3 06-backend/manage.py seed_integration_runs     # the five runs
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8075 --noreload &
 *   (cd 07-frontend && ./node_modules/.bin/vite build && \
 *      PORT=4275 API_PROXY_TARGET=http://127.0.0.1:8075 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4275 \
 *   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr069-c-run-record.mjs
 *
 * ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** It reads only — no
 * run is ever written by a screen — but `integration_run` is append-only, so a
 * neighbour's seeding would add rows this script counts.
 *
 * ── WHAT IT ASSERTS (demo script C, clicked) ──────────────────────────────
 *   1  Settings → Integrations: the Billing mailbox card carries the one link
 *      to S142, and a card with no connection carries none (law 2: wired).
 *   2  S142 for the Billing mailbox: five runs, newest first, in the product's
 *      ONE list assembly (`DataTable`: r10's toolbar, sortable header, icon
 *      row action, pagination footer), each with its support reference.
 *   3  The 1 August row reads **86 of 93 · 7 bad addresses**.
 *   4  Opening it NAMES the seven, each with the mailbox's own sentence — and
 *      its four tiles are numbers, because the far end confirmed.
 *   5  The 1 July row reads **Unconfirmed · 93 sent, provider did not say**,
 *      and opening it shows FOUR TILES OF WHICH THREE ARE DASHES.
 *   6  **The amber actually painted** — computed colour, and not the green.
 *   7  Support is read `a7f3c9e1`: one search finds the run, its connection
 *      and the mail server's own sentence (*535 5.7.8 AUTHENTICATION FAILED*).
 *   8  The leak-path run's `provider_error` is SCRUBBED on screen — no account
 *      number, no street, no other utility's name — and the server's list
 *      payload never carried it at all.
 *   9  The Integrations grid shows the mailbox as needing attention, not green.
 *  10  No `BR-` string, no rule id and no database id anywhere on the screen;
 *      no sideways scroll at 1440; screenshots of every step.
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4275";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr069-c-run-record";
const VIEWPORT = { width: 1440, height: 1000 };
const SMTP = "email_smtp";

/** The support reference the agent is read down the phone (sample_runs.DEMO_TRACE). */
const DEMO_TRACE = "A7F3C9E1";
/** The leak-path run (sample_runs.LEAK_TRACE). */
const LEAK_TRACE = "C4D5E6F7";

/** `--color-warning-700: #a65d0a` in src/styles/tailwind.css, as a browser reports it. */
const AMBER = "rgb(166, 93, 10)";
/** `--color-success-700: #0f6e3a` — the green *Unconfirmed* must never be. */
const GREEN = "rgb(15, 110, 58)";

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

const SIDEWAYS =
  "Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)";

const FORBIDDEN_IN_CLERK_COPY = [
  /\bBR-[A-Z]{3}-\d{3,5}\b/,
  /\bOQ-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /\bDEF-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /\bUS-[A-Z]{3}-\d{3,5}\b/,
  /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
];

/** The other utility's details that must never survive the scrub. */
const MUST_NOT_APPEAR = ["4471-0021", "Pecan St", "Lone Star Ridge", "lonestarridge.example"];

/** The row's own eye icon. `DataTable` owns the `<tr>` and puts nothing of a
 *  consumer's on it, so the row is addressed through the identity cell's hook
 *  and the action is found on the same row. */
async function openRun(page, trace) {
  await page
    .locator(`tr:has([data-run-row="${trace}"])`)
    .getByRole("button", { name: "Open the run" })
    .click();
  await page.waitForSelector("[data-run-card]", { timeout: 20000 });
}

/** The kit's search box — debounced, no Find button (r10 rule 12). */
async function searchFor(page, text) {
  const box = page.getByPlaceholder("Support reference");
  await box.fill("");
  await box.fill(text);
}

async function closeRun(page) {
  await page.getByRole("button", { name: "Close" }).click();
  await page.waitForSelector("[data-run-card]", { state: "detached", timeout: 20000 });
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });

  // What the SERVER actually served, so the counts on screen can be compared
  // with the payload rather than with themselves.
  let servedRuns = null;
  page.on("response", async (response) => {
    if (!/\/integrations\/[^/]+\/runs(?:\?|$)/.test(response.url())) return;
    try {
      servedRuns = JSON.parse(await response.text());
    } catch {
      // not JSON
    }
  });

  console.log(`cr069-c: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);

  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });
  console.log("   signed in");

  // ═════════════════════════════════════════════════════════════════════════
  // 1 · Settings → Integrations — the card's link, and the card's word
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 1 · Settings → Integrations ──");
  await page.goto(`${BASE}/${TENANT}/settings/integrations`, { waitUntil: "networkidle" });
  await page.waitForSelector(`[data-provider="${SMTP}"]`, { timeout: 20000 });
  await page.screenshot({ path: join(OUT, "1-grid.png"), fullPage: true });
  check(
    (await page.locator(`[data-activity-link="${SMTP}"]`).count()) === 1,
    "the Billing mailbox card carries the Recent activity link",
  );
  check(
    (await page.locator('[data-activity-link="payments_card"]').count()) === 0,
    "a card with no connection carries none — a link to an empty screen is not a feature",
  );

  // 9 · the grid's own word for a connection whose last run could not be confirmed
  const cardState = await page
    .locator(`[data-provider="${SMTP}"] [data-operation-state], [data-provider="${SMTP}"] [data-state]`)
    .first()
    .textContent()
    .catch(() => null);
  console.log(`   the mailbox card reads: ${JSON.stringify(cardState)}`);

  // ═════════════════════════════════════════════════════════════════════════
  // 2 · S142 for the Billing mailbox
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 2 · S142 · the Billing mailbox ──");
  await page.click(`[data-activity-link="${SMTP}"]`);
  await page.waitForSelector("[data-run-row]", { timeout: 20000 });
  check(
    page.url().endsWith(`/settings/integrations/${SMTP}`),
    `S142 has a URL of its own (${new URL(page.url()).pathname})`,
  );
  await page.screenshot({ path: join(OUT, "2-recent-activity.png"), fullPage: true });

  const traces = await page
    .locator("[data-run-row]")
    .evaluateAll((nodes) => nodes.map((n) => n.getAttribute("data-run-row")));
  check(traces.length === 5, `five runs drawn, newest first (${traces.length})`);
  check(traces[0] === DEMO_TRACE, `the newest is the manual test, ${traces[0]}`);
  check(traces.includes(LEAK_TRACE), "the leak-path run is in the list");

  if (servedRuns !== null) {
    const august = servedRuns.rows.find((one) => one.outcome === "partial");
    check(
      august !== undefined && august.attempted === 93 && august.succeeded === 86 && august.failed === 7,
      `the server served 93 attempted · 86 succeeded · 7 failed for the 1 August run`,
    );
    check(
      servedRuns.rows.every((one) => !("provider_error" in one)),
      "no row of the LIST payload carries provider_error — the mitigation, on the wire",
    );
    check(
      servedRuns.page.per === 50,
      `the product's own first page size (per = ${servedRuns.page.per}) — the design's ` +
        "twenty is a stamped deviation: one page-size vocabulary, one table assembly",
    );
  } else {
    check(false, "GET /integrations/{key}/runs was never observed");
  }

  // ═════════════════════════════════════════════════════════════════════════
  // 3 · the 1 August row
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 3 · the 1 August row ──");
  const augustRow = page.locator("[data-run-row][data-run-outcome='partial']");
  const augustTrace = await augustRow.getAttribute("data-run-row");
  const augustLine = await page.locator(`[data-run-counts="${augustTrace}"]`).textContent();
  check(
    augustLine === "86 of 93 · 7 bad addresses",
    `the row reads "${augustLine}" — the mailbox's own word for a refusal`,
  );

  // ═════════════════════════════════════════════════════════════════════════
  // 4 · opened: the seven, named
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 4 · the seven it could not send ──");
  await openRun(page, augustTrace);
  await page.screenshot({ path: join(OUT, "4-the-seven.png"), fullPage: true });
  const items = await page
    .locator("[data-run-item]")
    .evaluateAll((nodes) => nodes.map((n) => n.getAttribute("data-run-item")));
  check(items.length === 7, `seven items named (${items.length})`);
  check(
    items.every((one) => one.includes("@")),
    `each is an address a clerk can go and fix — ${items[0]}`,
  );
  const said = await page.locator("[data-run-item]").first().textContent();
  check(said.includes("No such mailbox"), `…with the mailbox's own sentence: "${said.trim()}"`);
  const augustTiles = await page
    .locator("[data-count-tile]")
    .evaluateAll((nodes) => nodes.map((n) => n.getAttribute("data-dashed")));
  check(
    augustTiles.length === 4 && augustTiles.every((one) => one === "false"),
    "four tiles, all NUMBERS — the far end confirmed this one",
  );
  await closeRun(page);

  // ═════════════════════════════════════════════════════════════════════════
  // 5 · 6 · the 1 July row — Unconfirmed, amber, dashes
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 5 · the run nobody designs for ──");
  const julyRow = page.locator("[data-run-row][data-run-outcome='unconfirmed']");
  const julyTrace = await julyRow.getAttribute("data-run-row");
  const julyCell = page.locator(`[data-run-counts="${julyTrace}"]`);
  const julyLine = await julyCell.textContent();
  check(
    julyLine === "Unconfirmed · 93 sent, provider did not say",
    `the row reads "${julyLine}"`,
  );

  const painted = await julyCell.evaluate((el) => {
    const s = getComputedStyle(el);
    return { colour: s.color, weight: s.fontWeight };
  });
  check(painted.colour === AMBER, `…in the theme's amber (${painted.colour})`);
  check(painted.colour !== GREEN, "…and it is not the green a finished run gets");
  const septemberTrace = (
    await page.locator("[data-run-row][data-run-outcome='succeeded']").getAttribute("data-run-row")
  );
  const septemberColour = await page
    .locator(`[data-run-counts="${septemberTrace}"]`)
    .evaluate((el) => getComputedStyle(el).color);
  check(
    septemberColour === GREEN,
    `…while the 1 September run, which the provider DID confirm, is green (${septemberColour})`,
  );

  await openRun(page, julyTrace);
  await page.screenshot({ path: join(OUT, "5-unconfirmed-dashes.png"), fullPage: true });
  const julyTiles = await page
    .locator("[data-count-tile]")
    .evaluateAll((nodes) =>
      nodes.map((n) => ({
        dashed: n.getAttribute("data-dashed"),
        value: n.querySelector("span")?.textContent,
      })),
    );
  check(julyTiles.length === 4, `four tiles (${julyTiles.length})`);
  check(
    julyTiles[0].value === "93" && julyTiles.slice(1).every((one) => one.value === "—"),
    `93 handed over, then three dashes — ${julyTiles.map((o) => o.value).join(" · ")}`,
  );
  check(
    julyTiles.slice(1).every((one) => one.dashed === "true"),
    "…and a zero is never shown where we do not know",
  );
  await closeRun(page);

  // ═════════════════════════════════════════════════════════════════════════
  // 7 · eight characters down the phone
  // ═════════════════════════════════════════════════════════════════════════
  console.log(`\n── 7 · support is read ${DEMO_TRACE.toLowerCase()} ──`);
  await searchFor(page, DEMO_TRACE.toLowerCase());
  await page.waitForFunction(
    () => document.querySelectorAll("[data-run-row]").length === 1,
    null,
    { timeout: 20000 },
  );
  await page.screenshot({ path: join(OUT, "7-found-by-trace.png"), fullPage: true });
  const found = await page
    .locator("[data-run-row]")
    .evaluateAll((nodes) => nodes.map((n) => n.getAttribute("data-run-row")));
  check(
    found.length === 1 && found[0] === DEMO_TRACE,
    `one run, and it is ${found[0]} — typed in lower case, found regardless`,
  );
  await openRun(page, DEMO_TRACE);
  const theirWords = await page.locator("[data-provider-said]").textContent();
  check(
    theirWords.trim() === "535 5.7.8 AUTHENTICATION FAILED",
    `the mail server's own sentence: "${theirWords.trim()}"`,
  );
  const ourSentence = await page.locator("[data-run-card]").textContent();
  check(
    ourSentence.includes("The mail server rejected the password."),
    "…with OUR sentence above it — one is actionable, the other is what support needs",
  );
  check(ourSentence.includes(DEMO_TRACE), "…and the support reference is on the card");
  await closeRun(page);

  // ═════════════════════════════════════════════════════════════════════════
  // 8 · the leak path, on screen
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 8 · another utility's customer, scrubbed ──");
  await searchFor(page, LEAK_TRACE);
  await page.waitForFunction(
    (t) => document.querySelector(`[data-run-row="${t}"]`) !== null,
    LEAK_TRACE,
    { timeout: 20000 },
  );
  await openRun(page, LEAK_TRACE);
  await page.screenshot({ path: join(OUT, "8-scrubbed.png"), fullPage: true });
  const leakText = await page.locator("[data-provider-said]").textContent();
  for (const secret of MUST_NOT_APPEAR) {
    check(!leakText.includes(secret), `the other utility's ${secret} is not on the screen`);
  }
  check(leakText.includes("••••"), `…it reads "${leakText.trim()}"`);
  check(leakText.includes("550 5.1.1"), "…and the provider's own code survived, which is the point");
  await closeRun(page);

  // ═════════════════════════════════════════════════════════════════════════
  // 9 · the grid is not green for this connection
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 9 · back to the grid ──");
  await page.goto(`${BASE}/${TENANT}/settings/integrations`, { waitUntil: "networkidle" });
  await page.waitForSelector(`[data-provider="${SMTP}"]`, { timeout: 20000 });
  await page.screenshot({ path: join(OUT, "9-grid-attention.png"), fullPage: true });
  const word = await page.locator(`[data-provider="${SMTP}"]`).innerText();
  check(!/\bWorking\b/.test(word), `the mailbox card does not read Working — it reads:\n      ${word.replace(/\n/g, " · ")}`);

  // ═════════════════════════════════════════════════════════════════════════
  // 10 · nothing internal, and no sideways scroll
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 10 · what a clerk can read ──");
  await page.goto(`${BASE}/${TENANT}/settings/integrations/${SMTP}`, { waitUntil: "networkidle" });
  await page.waitForSelector("[data-run-row]", { timeout: 20000 });
  const text = await page.evaluate(() => document.body.innerText);
  for (const pattern of FORBIDDEN_IN_CLERK_COPY) {
    const hit = text.match(pattern);
    check(hit === null, `no ${pattern} in clerk copy${hit ? ` — found ${hit[0]}` : ""}`);
  }
  const sideways = await page.evaluate(SIDEWAYS);
  check(sideways === 0, `no sideways scroll at ${VIEWPORT.width} (overflow ${sideways}px)`);

  await browser.close();

  console.log(`\nscreenshots: ${OUT}`);
  if (failures.length > 0) {
    console.log(`\n⛔ ${failures.length} failure(s)`);
    for (const f of failures) console.log(`   · ${f}`);
    process.exit(1);
  }
  console.log("\n✓ cr069 wave C: a run says what it did — and says Unconfirmed when it cannot");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
