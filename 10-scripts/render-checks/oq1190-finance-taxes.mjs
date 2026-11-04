#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Question: OQ-1190 — CLOSED 2026-08-31. PO verbatim: *"(a) Add a per-authority
//           subtotal to the bill and the finance screens"*. `cr053-bill-surface
//           .mjs` proves THE BILL half in a browser; this proves the FINANCE
//           half, which is the other surface the ruling names and which no
//           jsdom test can see.
//           Screen: S41 Taxes & Remittance (Finance → Taxes & Remittance)
// Rules:    BR-BIL-069 (each authority has its OWN 2200-nn account — the
//           account IS the authority's identity in the books) · BR-LED-013 ·
//           BR-SHL-023 (one money formatting path) · B14 rule 31 (no database
//           id is the visible value of a field) · PO 2026-08-30 (*"All UI
//           screen should be confirm using real broswer testing and not just
//           based on test cases"*) · hard-won law 6
// ───────────────────────────────────────────────────────
/**
 * Open S41 in a REAL browser and read the per-authority column back.
 *
 * ⚠ **WHY IT IS SEPARATE FROM THE BILL CHECK.** `cr053-bill-surface.mjs` signs
 * in and drives S30; S41 is a different screen behind a different permission
 * and a different period control, and bolting it onto that file would make a
 * bill-surface failure and a finance failure indistinguishable in one exit
 * code. Two screens, two checks.
 *
 * ⚠ **AND IT REPORTS WHAT IT COULD NOT EXERCISE RATHER THAN PASSING QUIETLY.**
 * A tenant whose books hold no tax-payable account draws an empty table, and
 * every assertion below would be trivially true over it. That is the shape of a
 * check that cannot fail — six of which this repo recorded in one day — so the
 * run says `NOT exercised` and exits non-zero instead.
 *
 * ── HOW TO RUN IT ────────────────────────────────────────────────────────
 *   SMOKE_BASE=http://127.0.0.1:4290 \
 *   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/oq1190-finance-taxes.mjs
 *
 * ── WHAT IT ASSERTS ──────────────────────────────────────────────────────
 *   1  THE AUTHORITY IS NAMED, not only its account. `GAP_TAX_AUTHORITY_NAME`
 *      is that the books cannot name an authority; the BILLS can, so the row
 *      carries "Bexar County Tax Office" above "2200-01 · Tax payable — …".
 *   2  THE BILL-SOURCED SUBTOTAL IS ON THE SCREEN and is the server's own
 *      figure — compared against `GET /finance/taxes` fetched in the same run.
 *   3  IT IS GREATER THAN ZERO where the server sent one. On a screen a return
 *      is filed from, 0.00 reads as "this authority is owed nothing".
 *   4  AN ABSENT FIGURE SAYS SO and is never drawn as 0.00.
 *   5  WHETHER THE BILLS AND THE BOOKS AGREE IS THE SERVER'S VERDICT, read off
 *      `data-agrees` rather than recomputed here.
 *   6  NO 2200-nn ACCOUNT UUID IS VISIBLE (B14 rule 31).
 *   7  THE PAGE DOES NOT SCROLL SIDEWAYS — the column was added to a table that
 *      already had seven, which is the cheapest way to break a finance screen
 *      and is invisible to every source-level check.
 */
import { existsSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

// Resolved the way `cr053-bill-surface.mjs` resolves it: `playwright-core` from
// the FRONTEND's node_modules, and the browser binary from wherever this host
// keeps it. A bare `import "playwright"` fails here - there is no playwright
// package at the repo root, and PLAYWRIGHT_BROWSERS_PATH alone does not put
// one there.
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4290";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";

const failures = [];
const notes = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}
function note(message) {
  console.log(`   ⊘ ${message}`);
  notes.push(message);
}

const READ_TABLE = `(() => {
  const cell = (el) => (el ? el.textContent.trim() : null);
  const rows = [...document.querySelectorAll("tbody tr")].map((tr) => ({
    authorityCell: cell(tr.children[0]),
    authorityName: cell(tr.querySelector('[data-fin="authority-name"]')),
    billed: cell(tr.children[1]),
    fromBills: cell(tr.querySelector('[data-fin="billed-from-bills"]')),
    agrees: (tr.querySelector('[data-fin="bills-vs-books"]') || {}).dataset
      ? tr.querySelector('[data-fin="bills-vs-books"]').getAttribute("data-agrees")
      : null,
    verdict: cell(tr.querySelector('[data-fin="bills-vs-books"]')),
  }));
  const headers = [...document.querySelectorAll("thead th")].map((th) => th.textContent.trim());
  return {
    headers,
    rows,
    bodyText: document.body.innerText,
    sideways: Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth),
  };
})()`;

(async () => {
  console.log(`oq1190-finance: ${BASE} tenant=${TENANT}`);
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });

  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  // ⚠ WAIT FOR THE URL TO LEAVE /signin, not merely for the network to go quiet.
  // `networkidle` settles while the form is still on screen, so every later
  // request goes out unauthenticated and the whole run reports 401s that read
  // like a broken endpoint. This wait is what the bill-surface check does and
  // it is the reason that one works.
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });
  console.log("   signed in");

  // ⚠ THE SERVER'S ANSWER IS CAPTURED FROM THE SCREEN'S OWN REQUEST, never
  // re-fetched from inside the page. A second `fetch()` carries no Authorization
  // header — this session's token lives in the client, not in a cookie — and
  // answers 401, which reads exactly like a broken endpoint. Listening to the
  // real response is also the stronger check: it compares the screen against
  // what the screen was actually GIVEN.
  let served = { error: "no /finance/taxes response was observed" };
  page.on("response", async (response) => {
    // The API call, NOT the page navigation — the browser's own URL for
    // this screen also ends "/finance/taxes", and matching it caught an HTML
    // document and reported "the response was not JSON".
    if (!/\/api\/[^/]+\/finance\/taxes/.test(response.url())) return;
    if (!response.ok()) {
      served = { error: response.status() };
      return;
    }
    try {
      served = await response.json();
    } catch {
      served = { error: "the response was not JSON" };
    }
  });

  await page.goto(`${BASE}/${TENANT}/finance/taxes`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  const drawn = await page.evaluate(READ_TABLE);

  if (served.error) {
    check(false, `GET /finance/taxes answered ${served.error}`);
  } else if (!served.rows || served.rows.length === 0) {
    note(
      "this tenant's books hold no tax-payable account, so every per-authority " +
        "assertion would be trivially true — seed a taxed bill and re-run",
    );
  } else {
    check(
      drawn.headers.includes("Billed on bills"),
      `OQ-1190: the bill-sourced column is on the table (${drawn.headers.join(" · ")})`,
    );
    for (const row of served.rows) {
      const onScreen = drawn.rows.find((r) => (r.authorityCell || "").includes(row.code));
      check(onScreen !== undefined, `OQ-1190: account ${row.code} has a row on screen`);
      if (onScreen === undefined) continue;

      if (row.authority_name === null) {
        check(
          onScreen.authorityName === null,
          `OQ-1190: ${row.code}'s authority is UNNAMED and the screen says so ` +
            `("${onScreen.authorityCell}")`,
        );
      } else {
        check(
          onScreen.authorityName === row.authority_name,
          `OQ-1190: ${row.code} names its authority as rating knows it ` +
            `("${onScreen.authorityName}" vs served "${row.authority_name}")`,
        );
      }

      if (row.billed_from_bills === null) {
        check(
          (onScreen.fromBills || "").includes("No bill-side figure"),
          `OQ-1190: ${row.code}'s absent bill-side figure SAYS SO and is not 0.00 ` +
            `("${onScreen.fromBills}")`,
        );
      } else {
        const expected = Number(row.billed_from_bills).toFixed(2);
        check(
          (onScreen.fromBills || "").includes(expected),
          `OQ-1190: ${row.code} shows the SERVER's figure ${expected} ("${onScreen.fromBills}")`,
        );
        check(
          Number(row.billed_from_bills) > 0,
          `OQ-1190: ${row.code}'s bill-sourced figure is greater than zero ` +
            `(${row.billed_from_bills}) — 0.00 on a screen a return is filed from reads ` +
            `as "this authority is owed nothing"`,
        );
        check(
          String(row.bills_agree) === onScreen.agrees,
          `OQ-1190: the bills-vs-books verdict is the SERVER's (${onScreen.agrees}) — ` +
            `"${onScreen.verdict}"`,
        );
      }

      // B14 rule 31 — the account's UUID is the join key and never a value.
      check(
        !drawn.bodyText.includes(row.account_id),
        `B14 rule 31: ${row.code}'s database id is not visible on the page`,
      );
    }
  }

  check(drawn.sideways === 0, `S41 does not scroll sideways (${drawn.sideways}px)`);

  await browser.close();
  if (notes.length > 0) {
    console.log(`\n⊘ ${notes.length} assertion group(s) NOT exercised by this data:`);
    for (const n of notes) console.log(`   · ${n}`);
  }
  if (failures.length > 0 || notes.length > 0) {
    if (failures.length > 0) {
      console.log(`\n⛔ ${failures.length} failure(s):`);
      for (const f of failures) console.log(`   · ${f}`);
    }
    process.exit(1);
  }
  console.log("\n✓ every assertion held in a real browser");
})();
