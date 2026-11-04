/**
 * RENDERED-OUTPUT CHECK — CR-069 wave A, the Integrations grid, in a real browser.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: no gate in this repository looks at
 * rendered output, and nine defects in one day were found this way and by
 * nothing else. PO ruling 2026-09-03: *"ensure you do web walkthorugh before
 * you sign off the user story or build"*. A story is not signed off until this
 * has run green against a running product.
 *
 * ⚠ **AND B14 RULE 21 MAKES IT UNAVOIDABLE HERE.** A Tailwind utility is
 * emitted ONLY for a file listed in `07-frontend/src/styles/route-b-migrated.txt`.
 * Write one in a file that is not on that list and it is a class no stylesheet
 * declares: the screen renders as unstyled text, and `tsc`, eslint and every
 * `toContain("flex")` assertion pass on it because the class IS in the DOM.
 * `features/integrations/IntegrationsTab.tsx` was added to that list in the
 * same commit that created it, and **the only thing that can prove the rules
 * actually compiled is computed style in a real engine** — step 6 below.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   createdb sbh_cr069a
 *   DATABASE_URL=…/sbh_cr069a python3 06-backend/manage.py migrate
 *   DATABASE_URL=…/sbh_cr069a python3 06-backend/manage.py seed_demo
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local \
 *   DATABASE_URL="postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_cr069a" \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8069 --noreload &
 *   (cd 07-frontend && npx vite build && \
 *      PORT=4269 API_PROXY_TARGET=http://127.0.0.1:8069 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4269 \
 *   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr069-a-grid-not-set-up.mjs
 *
 * ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** The shared
 * development database is reseeded by other lanes, and a mid-run reseed looks
 * exactly like a broken screen.
 *
 * ── WHAT IT ASSERTS (demo script A, clicked) ──────────────────────────────
 *   1  **THE DECLARED-ABSENCE BOX IS GONE.** The tab said *"Accounting,
 *      payment, meter and email connections arrive with the Integrations
 *      feature. No connection can be made from here yet"* in all eleven
 *      catalogues. A string claiming a state of the product is a claim
 *      (hard-won law 1), and it stopped being true the moment the grid drew.
 *   2  **EVERY CARD COMES FROM THE REGISTRY (BR-INT-037).** The count on screen
 *      equals the count the server served — not a number typed into React.
 *   3  **EVERY CARD READS *Not set up* ON A FRESH TENANT**, because nothing has
 *      been connected. A card claiming otherwise would be inventing state.
 *   4  **A MULTI-OPERATION CARD SHOWS ITS OPERATIONS AND NO AGGREGATE WORD**
 *      (BR-INT-028). *"3 of 3 running"* is a claim about a thing that is not a
 *      thing.
 *   5  **NO DATABASE ID AND NO INTERNAL REFERENCE REACHES A CLERK** (B14 rules
 *      31 and 32).
 *   6  **THE UTILITIES COMPILED**, read as computed style in a real engine —
 *      the rule-21 trap above.
 *   7  **NO SIDEWAYS SCROLL AT 1440.**
 */

import { execFileSync } from "node:child_process";
import { mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const require = createRequire(join(process.cwd(), "07-frontend", "package.json"));
function requireFrontend(name) {
  return require(name);
}

const { chromium } = requireFrontend("playwright-core");

function resolveChromium() {
  const wanted = chromium.executablePath();
  try {
    execFileSync(wanted, ["--version"], { stdio: "ignore" });
    return wanted;
  } catch {
    // The pinned build is absent; fall back to the image's own browser.
    const root = process.env.PLAYWRIGHT_BROWSERS_PATH ?? "/opt/pw-browsers";
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const candidate of [
        join(root, dir, "chrome-linux", "chrome"),
        join(root, dir),
      ]) {
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4269";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr069-a-grid";
const VIEWPORT = { width: 1440, height: 1000 };

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

const SIDEWAYS =
  "Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)";

/** The sentence the tab carried until this wave. Its absence IS the deliverable. */
const ABSENCE_SENTENCES = [
  "arrive with the Integrations feature",
  "No connection can be made from here yet",
];

/** Anything a clerk must never be shown (B14 rules 31 and 32). */
const FORBIDDEN_IN_CLERK_COPY = [
  /\bBR-[A-Z]{3}-\d{3,5}\b/,
  /\bOQ-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /\bDEF-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
];

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });

  // The server's own answer, captured rather than inferred: "did the screen
  // draw seventeen cards" and "did the server serve seventeen" are two
  // different questions, and BR-INT-037 is about the second one.
  let served = null;
  page.on("response", async (response) => {
    if (!/\/integrations(?:\?|$)/.test(response.url())) return;
    try {
      served = JSON.parse(await response.text());
    } catch {
      // a redirect or a non-JSON body has nothing to read
    }
  });

  console.log(`cr069-a: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);

  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });
  console.log("   signed in");

  // ═════════════════════════════════════════════════════════════════════════
  // Settings → Integrations
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── Settings → Integrations ──");
  await page.goto(`${BASE}/${TENANT}/settings/integrations`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: join(OUT, "integrations-grid.png"), fullPage: true });

  const text = await page.evaluate(() => document.body.innerText);

  // 1 · the declared absence is gone
  for (const sentence of ABSENCE_SENTENCES) {
    check(!text.includes(sentence), `the absence sentence is gone: "${sentence.slice(0, 40)}…"`);
  }

  // 2 · every card came from the registry
  const cards = await page.locator("[data-provider]").count();
  check(cards > 0, `the grid drew ${cards} provider card(s)`);
  if (served !== null) {
    check(
      cards === served.providers.length,
      `the screen drew what the server served (${cards} = ${served.providers.length}) — BR-INT-037`,
    );
  } else {
    check(false, "GET /integrations was never observed — the grid may be drawing from React");
  }

  // 3 · a fresh tenant has connected nothing, so every word reads Not set up
  const states = await page.locator("[data-state]").evaluateAll((nodes) =>
    nodes.map((n) => n.getAttribute("data-state")),
  );
  check(states.length > 0, `${states.length} state word(s) rendered`);
  check(
    states.every((s) => s === "not_set_up"),
    `every state word reads Not set up on a fresh tenant (${new Set(states).size} distinct)`,
  );

  // 4 · a multi-operation card lists its operations and invents no headline
  const multi = await page.locator("[data-operations]").count();
  check(multi > 0, `${multi} multi-operation card(s) list their operations`);
  check(
    !/\b\d+\s+of\s+\d+\s+running\b/i.test(text),
    "no aggregate word over a multi-operation card (BR-INT-028)",
  );

  // 5 · nothing internal reaches the clerk
  for (const pattern of FORBIDDEN_IN_CLERK_COPY) {
    const hit = text.match(pattern);
    check(hit === null, `no ${pattern} in clerk copy${hit ? ` — found ${hit[0]}` : ""}`);
  }

  // 6 · the utilities actually compiled (rule 21 / DEF-974)
  const style = await page.locator("[data-provider]").first().evaluate((el) => {
    const s = getComputedStyle(el);
    return { display: s.display, borderStyle: s.borderTopStyle, padding: s.paddingTop };
  });
  check(
    style.display === "flex",
    `the card's Tailwind utilities compiled — display is ${style.display}, expected flex`,
  );
  check(
    style.padding !== "0px",
    `the card has real padding (${style.padding}) rather than an undeclared class`,
  );

  // 7 · no sideways scroll
  const sideways = await page.evaluate(SIDEWAYS);
  check(sideways === 0, `no sideways scroll at ${VIEWPORT.width} (overflow ${sideways}px)`);

  await browser.close();

  console.log(`\nscreenshots: ${OUT}`);
  if (failures.length > 0) {
    console.log(`\n⛔ ${failures.length} failure(s)`);
    for (const f of failures) console.log(`   · ${f}`);
    process.exit(1);
  }
  console.log("\n✓ cr069 wave A: the grid tells the truth");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
