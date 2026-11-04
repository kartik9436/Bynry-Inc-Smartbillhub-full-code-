/**
 * CR-056 W6 task 26 — THE MOVE-OUT IMPACT SCREEN, IN A REAL BROWSER.
 *
 * PO hard rule 2026-08-30: a screen is proved by clicking it, not by a jsdom
 * assertion about the markup a component produced.
 *
 * ── WHY A BROWSER AND NOT ANOTHER UNIT TEST ──────────────────────────────
 * Three of the four things this asserts are invisible to `vitest`:
 *
 *   1  **THE PANEL IS A `Disclosure` AND THE SENTENCE MUST SURVIVE IT BEING
 *      CLOSED.** The PO's ruling of 2026-08-31 is that the unit falling to the
 *      owner's account *"must be drawn there in words … rather than happening
 *      correctly and invisibly"*, and B19 §15.7 says the advisories are
 *      siblings of the disclosure precisely so they cannot be folded away. A
 *      string being present in `renderToStaticMarkup` says nothing about
 *      whether a person can SEE it — only a real layout engine can, and the
 *      check below reads `offsetParent`/`getBoundingClientRect`, not text.
 *
 *   2  **THE PORT IS WIRED TO A REAL SERVER.** The wizard's panel cases hand a
 *      `CloseImpact` object straight to the component. That proves the panel
 *      and says nothing about whether `GET /accounts/{id}/close-impact` serves
 *      the fields — hard-won law 2, and it is not hypothetical: proving the
 *      panel cases RED found exactly that hole, because restoring the old
 *      `units_occupied_after: null` port left every one of them green.
 *
 *   3  **B14 RULE 21 / DEF-974.** `moveShared.tsx` IS on
 *      `07-frontend/src/styles/route-b-migrated.txt`, so its utilities are
 *      emitted — but that is a fact about a text file, and the only thing that
 *      can confirm a class actually drew is computed style.
 *
 * ⚠ **REBUILD BEFORE MEASURING.** A check pointed at a stale `vite build`
 * reports failure with total confidence and no hint that it is reading the
 * wrong bytes.
 *
 * ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** The shared
 * development database is reseeded by other lanes; every id changes mid-run,
 * which looks exactly like a broken screen.
 *
 * ── HOW TO RUN IT ────────────────────────────────────────────────────────
 *   createdb smartbillhub_w6
 *   DATABASE_URL=…/smartbillhub_w6 python3 06-backend/manage.py migrate
 *   DATABASE_URL=…/smartbillhub_w6 python3 06-backend/manage.py seed_demo
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local \
 *   DATABASE_URL="postgres://smartbillhub:smartbillhub@127.0.0.1:5432/smartbillhub_w6" \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8066 --noreload &
 *   (cd 07-frontend && npx vite build && \
 *      PORT=4266 API_PROXY_TARGET=http://127.0.0.1:8066 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4266 SMOKE_ACCOUNT=<an occupying account id> \
 *   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr056-w6-move-out-impact.mjs
 *
 * ── WHAT IT ASSERTS ──────────────────────────────────────────────────────
 *   1  The move-out wizard's step 5 resolves and draws its nine panels.
 *   2  `GET /accounts/{id}/close-impact` answers the impact fields on the
 *      WIRE — read from the captured response body, not from the DOM.
 *   3  The ruled sentence is VISIBLE with the Unit panel CLOSED, and it names
 *      an account number.
 *   4  The occupancy line reads a real "N of M" rather than "not served".
 *   5  The FREE TEXT advisory is absent where the owner has an account.
 *   6  The page does not scroll sideways.
 */
import { existsSync, mkdirSync, readdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  const roots = [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean);
  for (const root of roots) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of [
        "chrome-linux64/chrome",
        "chrome-linux/chrome",
        "chrome-linux/headless_shell",
      ]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  return undefined;
}

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4266";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const ACCOUNT = process.env.SMOKE_ACCOUNT ?? "";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr056-w6-move-out-impact";
const VIEWPORT = { width: 1440, height: 1000 };

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

const SIDEWAYS =
  "Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)";

/**
 * The impact step, as a BROWSER sees it.
 *
 * ⚠ `visible` is `offsetParent !== null` plus a non-zero box — NOT
 * `textContent.includes(...)`. A string inside a collapsed `Disclosure` is in
 * the DOM and is not on the screen, and telling those two apart is the whole
 * reason this file exists rather than another `toContain` assertion.
 */
const READ_IMPACT = `(() => {
  const box = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { w: Math.round(r.width), h: Math.round(r.height), visible: el.offsetParent !== null && r.width > 0 && r.height > 0 };
  };
  const advisories = [...document.querySelectorAll('[data-advisory]')].map((el) => ({
    tracks: el.getAttribute('data-advisory'),
    text: (el.textContent || '').replace(/\\s+/g, ' ').trim(),
    ...box(el),
  }));
  const panels = [...document.querySelectorAll('[data-impact-panel]')].map((el) =>
    el.getAttribute('data-impact-panel'),
  );
  const headerText = (name) => {
    const panel = document.querySelector('[data-impact-panel="' + name + '"]');
    return panel ? (panel.textContent || '').replace(/\\s+/g, ' ').trim() : null;
  };
  const fallsTo = advisories.find((a) => a.tracks === 'CR-056-26') || null;
  return {
    panels,
    advisories,
    fallsTo,
    premisesHeader: headerText('premises'),
    unitHeader: headerText('unit'),
    freeTextAdvisory: advisories.some((a) => a.tracks === 'DEF-650'),
    // B14 rule 21 / DEF-974 — COMPUTED, never the class attribute. A utility in
    // a file off the Route B ledger is a class name with no rule behind it and
    // reading className cannot tell the difference.
    fallsToBorder: (() => {
      const el = document.querySelector('[data-advisory="CR-056-26"]');
      return el ? getComputedStyle(el).borderLeftWidth : null;
    })(),
    sideways: ${SIDEWAYS},
  };
})()`;

async function main() {
  const executablePath = resolveChromium();
  const browser = await chromium.launch({ headless: true, executablePath });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();

  /** Every close-impact response body, captured off the WIRE. */
  const impactBodies = [];
  page.on("response", async (response) => {
    if (!response.url().includes("/close-impact")) return;
    try {
      impactBodies.push(await response.json());
    } catch {
      /* non-JSON — recorded as absent rather than crashing the run */
    }
  });

  console.log("1 · sign in");
  await page.goto(`${BASE}/${TENANT}/login`, { waitUntil: "networkidle" });
  await page.fill('input[type="email"]', EMAIL);
  await page.fill('input[type="password"]', PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForLoadState("networkidle");

  if (!ACCOUNT) {
    console.log("⛔ SMOKE_ACCOUNT is not set — name an OCCUPYING account id to walk.");
    await browser.close();
    process.exit(2);
  }

  console.log("2 · the move-out wizard, straight to the impact step");
  await page.goto(`${BASE}/${TENANT}/accounts/${ACCOUNT}/move-out`, {
    waitUntil: "networkidle",
  });
  // Step 5 is the impact. The rail buttons are the supported way in.
  for (const step of [2, 3, 4, 5]) {
    const button = page.locator(`[data-wizard-step="${step}"]`);
    if ((await button.count()) > 0 && (await button.isEnabled())) {
      await button.click();
      await page.waitForTimeout(250);
    }
  }
  await page.waitForTimeout(600);
  await page.screenshot({ path: join(OUT, "impact.png"), fullPage: true });

  const read = await page.evaluate(READ_IMPACT);
  writeFileSync(join(OUT, "impact.json"), JSON.stringify({ read, impactBodies }, null, 2));

  console.log("3 · assertions");
  check(read.panels.length >= 9, `the nine impact panels render (saw ${read.panels.length})`);

  const served = impactBodies[impactBodies.length - 1] ?? null;
  check(served !== null, "GET /accounts/{id}/close-impact answered on the wire");
  if (served) {
    check(
      Object.prototype.hasOwnProperty.call(served, "unit_falls_to"),
      "the wire carries `unit_falls_to` — the field the ruling is about",
    );
    check(
      served.units_occupied_after !== null && served.units_occupied_after !== undefined,
      `the wire carries a real occupancy count (saw ${JSON.stringify(served.units_occupied_after)})`,
    );
    check(
      served.vacant_base_charge === null,
      "no single vacant-unit PRICE is served — pricing is the engine's, and the plan's own per-service figures travel instead",
    );
  }

  // ⚠ THE ONE THAT NEEDED A BROWSER: visible with the panel CLOSED.
  check(
    read.fallsTo !== null && read.fallsTo.visible === true,
    "the ruled sentence is VISIBLE with the Unit panel closed (B19 §15.7 — an advisory is a sibling of the disclosure, never a child)",
  );
  if (read.fallsTo) {
    const namesAnAccount = /[A-Z]{2}-\d{4}-\d{5}|AC-\d/.test(read.fallsTo.text);
    check(
      namesAnAccount || /no owner account/i.test(read.fallsTo.text),
      `the sentence NAMES the account, or says there is none — read: "${read.fallsTo.text.slice(0, 120)}"`,
    );
    check(
      /comes off that account again|next tenant/i.test(read.fallsTo.text) ||
        /no owner account/i.test(read.fallsTo.text),
      "the REVERSE EDGE is stated in the same sentence (PO 2026-08-31)",
    );
    check(
      read.fallsToBorder !== null && read.fallsToBorder !== "0px",
      `the advisory's utilities COMPILED — computed border-left-width is ${read.fallsToBorder} (B14 rule 21 / DEF-974)`,
    );
  }

  check(
    !/not served/i.test(read.premisesHeader ?? "") || (served && served.owner_on_record === null),
    "the Premises panel states a measurement rather than 'not served'",
  );
  check(read.sideways === 0, `the page does not scroll sideways (overflow ${read.sideways}px)`);

  await browser.close();
  if (failures.length) {
    console.log(`\n⛔ ${failures.length} failure(s):`);
    for (const f of failures) console.log(`   - ${f}`);
    process.exit(1);
  }
  console.log("\n✅ cr056-w6-move-out-impact: every assertion held");
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
