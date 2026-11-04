/**
 * RENDERED-OUTPUT CHECK — US-AUD-010 / TC-RBS-12, in a real browser, against
 * the running product. **A CLERK OPENS AN ACCOUNT'S HISTORY AND READS WHICH
 * AUTOMATION CHARGED THE FEE.**
 *
 * ⚠ **WHY THIS EXISTS.** The returned-payments runbook applies a $25 fee to 43
 * accounts overnight — $1,075 charged while nobody is at the office. Six weeks
 * later a customer disputes theirs and a clerk opens the account history.
 * Before `US-AUD-010` she saw one of two things and both are wrong: a **blank
 * actor**, indistinguishable from a bill run, an import or a bug, so she can
 * tell the customer nothing — or **a colleague's name**, because the automation
 * borrowed the login of whoever set it up. It must read
 * **"Returned payments, version 4"**.
 *
 * ⚠ **NO GATE IN THIS REPOSITORY LOOKS AT RENDERED OUTPUT** (CLAUDE.md
 * hard-won law 6), and the unit tests here assert a FUNCTION's return value.
 * That is not the same claim as "the sentence reached the clerk's screen":
 * `DEF-SHL-3964` is exactly the gap between the two. This file closes it by
 * asking the browser.
 *
 * ⚠ **THE ASSERTION THAT EARNS ITS PLACE IS THE NEGATIVE ONE.** The failure
 * this story removes is not "the name is missing" — it is "somebody ELSE'S name
 * is there". So the Actor cell is checked to contain neither a staff member's
 * name nor a uuid, on a screen where staff names are drawn one row away.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   createdb sbh_aud010_smoke
 *   DJANGO_SETTINGS_MODULE=config.settings.local \
 *   DATABASE_URL="postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_aud010_smoke" \
 *     python3 06-backend/manage.py migrate && \
 *     python3 06-backend/manage.py seed_demo
 *   # plant the runbook's audit row (this script's own fixture step is in
 *   # 10-scripts/render-checks/us_aud_010_seed.py — run it against the SAME url)
 *   DJANGO_SETTINGS_MODULE=config.settings.local DATABASE_URL=… \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8144 --noreload &
 *   (cd 07-frontend && npx vite build && \
 *      STATIC_DIR=$PWD/dist PORT=4344 API_PROXY_TARGET=http://127.0.0.1:8144 \
 *      node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4344 SMOKE_ACCOUNT=<the id the seed printed> \
 *     node 10-scripts/render-checks/us-aud-010-the-audit-actor.mjs
 *
 * ⚠ **REBUILD THE BUNDLE. DO NOT TRUST A RUNNING ONE** — a stale `dist` from
 * another lane looks exactly like a fix that did not work.
 *
 * ── WHAT IT DOES ──────────────────────────────────────────────────────────
 *   1  Open S61, the audit log, and find the runbook's row.
 *   2  Read its Actor cell and require the NAME AND THE VERSION.
 *   3  Require that the same cell holds no staff name and no uuid.
 *   4  Prove a person's row and an unnamed system job still read as they did —
 *      the story adds a third answer, it does not move the other two.
 *   5  Open the account's own History tab (the screen the scenario names) and
 *      require the SAME sentence there — BR-AUD-010, one audit surface.
 *   6  Use the Automations filter, because a server filter no control can
 *      select is a feature that does not exist (hard-won law 2).
 */
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";

const require = createRequire(new URL("../../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright-core");

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4344";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "owner@brazosbend.test";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "Brazos!passw0rd";
const OUT = process.env.SMOKE_OUT ?? "/tmp/us-aud-010";
/** The account `us_aud_010_seed.py` planted the row on. Named, never guessed — see step 4. */
const ACCOUNT = process.env.SMOKE_ACCOUNT ?? "";

/** What the clerk must read. Both halves — a name without its version is half an answer. */
const EXPECTED = "Returned payments, version 4";
/** What she used to read, and must not any more. */
const OLD_BLANK = "System job";

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

const UUID_SHAPED = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;

async function signIn(page) {
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
}

/**
 * Every row of the drawn audit table as {actor, action}.
 *
 * ⚠ IT READS THE TABLE THE BROWSER ACTUALLY PAINTED, not the API. Reading the
 * API here would re-assert what the backend suite already proves and would pass
 * happily over a screen that draws none of it — the exact shape of a check
 * looking at the wrong thing.
 */
async function rows(page) {
  return page.evaluate(() => {
    const out = [];
    for (const table of document.querySelectorAll("table")) {
      const heads = [...table.querySelectorAll("thead th")].map((th) =>
        (th.textContent ?? "").trim().toLowerCase(),
      );
      const actorAt = heads.indexOf("actor");
      const actionAt = heads.indexOf("action");
      if (actorAt < 0) continue;
      for (const tr of table.querySelectorAll("tbody tr")) {
        const cells = [...tr.querySelectorAll("td")];
        if (cells.length <= actorAt) continue;
        out.push({
          actor: (cells[actorAt].textContent ?? "").trim(),
          action: actionAt >= 0 && cells[actionAt] ? (cells[actionAt].textContent ?? "").trim() : "",
        });
      }
    }
    return out;
  });
}

async function main() {
  mkdirSync(OUT, { recursive: true });
  const executablePath =
    process.env.SMOKE_CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
  const browser = await chromium.launch({ executablePath });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();

  try {
    console.log("0 · sign in");
    await signIn(page);

    console.log("1 · S61 — the audit log, filtered to automations");
    await page.goto(`${BASE}/${TENANT}/audit-log?f.actor=automation`, {
      waitUntil: "networkidle",
    });
    await page.waitForTimeout(1200);
    await page.screenshot({ path: `${OUT}/01-audit-log-automations.png`, fullPage: true });
    const automationRows = await rows(page);
    check(
      automationRows.length > 0,
      `the Automations filter returned rows (${automationRows.length}) — ` +
        "a server filter no control can select is a feature that does not exist",
    );

    console.log("2 · the actor cell");
    const runbook = automationRows.find((r) => r.actor.includes("Returned payments"));
    check(runbook !== undefined, "a row whose Actor names the runbook is on screen");
    if (runbook) {
      check(runbook.actor === EXPECTED, `the Actor cell reads "${EXPECTED}" (got "${runbook.actor}")`);
      check(runbook.actor !== OLD_BLANK, `it is NOT "${OLD_BLANK}" — the blank this story removes`);
      check(
        !UUID_SHAPED.test(runbook.actor),
        "no database id is the visible value of the field (B14 rule 31)",
      );
    }

    console.log("3 · the whole page, unfiltered — the other two answers must not have moved");
    await page.goto(`${BASE}/${TENANT}/audit-log`, { waitUntil: "networkidle" });
    await page.waitForTimeout(1200);
    await page.screenshot({ path: `${OUT}/02-audit-log-all.png`, fullPage: true });
    const all = await rows(page);
    const staffNames = all
      .map((r) => r.actor)
      .filter((a) => a && a !== OLD_BLANK && !a.includes("Returned payments"));
    check(staffNames.length > 0, `staff-name rows are still drawn beside it (${staffNames.length})`);
    const named = all.find((r) => r.actor.includes("Returned payments"));
    if (named) {
      // THE ASSERTION THAT MATTERS: on a page where staff names ARE drawn, the
      // automation's own cell holds none of them.
      const borrowed = staffNames.find((n) => named.actor.includes(n));
      check(
        borrowed === undefined,
        `the automation's cell borrows no colleague's name (checked against ${staffNames.length})`,
      );
    }

    console.log("4 · the account history — BR-AUD-010, one audit surface");
    // ⚠ THE ACCOUNT IS NAMED, NOT GUESSED, AND THE FIRST DRAFT GUESSED. It
    // opened whatever account the list happened to sort first — `AC-2026-00001`
    // — whose history has no runbook row and never would. The check went red
    // over the wrong account and read exactly like a broken feature: law 7's
    // "looking at the wrong thing", on its first run. `us_aud_010_seed.py`
    // prints the export line for this.
    if (!ACCOUNT) {
      check(
        false,
        "SMOKE_ACCOUNT is not set — run us_aud_010_seed.py and export the id it prints. " +
          "This check will NOT fall back to an arbitrary account: opening the wrong one " +
          "produces a red that means nothing",
      );
    } else {
      await page.goto(`${BASE}/${TENANT}/accounts/${ACCOUNT}?tab=audit`, {
        waitUntil: "networkidle",
      });
      await page.waitForTimeout(1500);
      await page.screenshot({ path: `${OUT}/03-account-history.png`, fullPage: true });
      const historyRows = await rows(page);
      check(historyRows.length > 0, `the History tab drew its table (${historyRows.length} rows)`);
      const onHistory = historyRows.find((r) => r.actor.includes("Returned payments"));
      check(
        onHistory !== undefined,
        "the account's own History tab names the runbook too (BR-AUD-010)",
      );
      if (onHistory) {
        check(onHistory.actor === EXPECTED, `and reads the same sentence: "${EXPECTED}"`);
      }
      // The three answers, side by side on one screen — which is the only place
      // "it did not take the other two with it" can actually be seen.
      check(
        historyRows.some((r) => r.actor === OLD_BLANK),
        "an UNNAMED system job still reads 'System job' on the same table (BR-AUD-003)",
      );
      check(
        historyRows.some(
          (r) => r.actor && r.actor !== OLD_BLANK && !r.actor.includes("Returned payments"),
        ),
        "and a person still reads as their own name on the same table",
      );
    }
  } finally {
    await browser.close();
  }

  console.log("");
  if (failures.length) {
    console.log(`⛔ ${failures.length} failure(s):`);
    for (const f of failures) console.log(`   - ${f}`);
    process.exitCode = 1;
  } else {
    console.log(`✓ US-AUD-010 · TC-RBS-12 — screenshots in ${OUT}`);
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
