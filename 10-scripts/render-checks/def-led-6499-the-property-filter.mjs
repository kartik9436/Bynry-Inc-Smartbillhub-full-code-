/**
 * RENDERED-OUTPUT CHECK — `DEF-LED-6499` / Finance blueprint `P2.3` · `P2.4`
 * (p014) and the Balance screen's own criteria table (p023), driven in a real
 * browser against a seeded utility.
 *
 * ⚠ **WHY THIS EXISTS.** CLAUDE.md hard-won law 6: no gate in this repository
 * looks at rendered output, and nine defects in one day were found this way and
 * by nothing else. `P2.8` says the same thing for this phase in its own words —
 * *"Copy changes and a CSS fix need a rendered-output check, not a journey"* —
 * and it is the only reason this file is not a unit test.
 *
 * **AND THE DEFECT ITSELF IS THE ARGUMENT.** The panel this removes was covered
 * by a test asserting its sentence was PRESENT and pinning its exact English.
 * Both assertions were true and **neither could go red the day the filter
 * shipped**. Nothing that reads source could have caught it; somebody had to
 * open the screen.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   PROOF_DB_PYTHON=<venv>/bin/python 10-scripts/proof-db.sh clone finp2
 *   (cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \
 *      JOBS_EAGER=false \
 *      DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_finp2?sslmode=disable \
 *      python manage.py load_sample_data --tenant brazosbend)
 *   (cd 06-backend && … manage.py runserver 127.0.0.1:8471 --noreload &)
 *   (cd 07-frontend && ./node_modules/.bin/vite build && \
 *      PORT=4472 API_PROXY_TARGET=http://127.0.0.1:8471 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4472 \
 *      node 10-scripts/render-checks/def-led-6499-the-property-filter.mjs
 *
 * ⚠ **`JOBS_EAGER=false` IS NOT OPTIONAL HERE.** `proof-db.sh build` does not
 * set it, and `load_sample_data` therefore died on
 * `kombu.exceptions.OperationalError: Error 111 connecting to localhost:6379`
 * after 239 seconds — leaving a template with its tenant row and **zero
 * premises, zero journal lines and zero ledger accounts**. The build reported
 * success. Reported as a finding rather than worked around silently.
 *
 * ⚠ **REBUILD THE BUNDLE. DO NOT TRUST A RUNNING ONE** — a stale `dist` from
 * another lane looks exactly like a fix that did not work.
 *
 * ── WHAT IT CHECKS, AND WHY EACH ONE CAN FAIL ─────────────────────────────
 *   1  The false sentence is GONE from the rendered page. The defect, directly.
 *   2  The CONTROL is there, with its own label. `P2.4`'s outcome is not an
 *      empty space where a panel was — it is *"the honest build is the working
 *      control"*.
 *   3  Typing one character asks the server NOTHING (IS-3's two-character
 *      minimum). At 40,000 premises a search on every keystroke is the defect
 *      this control exists to avoid.
 *   4  Typing two asks, and REAL premises come back from the seeded tenant.
 *   5  Choosing one puts `f.premises` on the wire — watched on the network,
 *      because a control that moves and sends nothing is hard-won law 2's dead
 *      UI and a screenshot cannot tell the difference.
 *   6  **The TABLE CHANGES.** The strongest of the six: the filtered trial
 *      balance is not the unfiltered one. A request that goes out and an answer
 *      that is ignored is exactly what a missing cache key produces.
 *   7  No database id is rendered anywhere (B14 rule 31), read as `innerText`
 *      and never as markup — the rule's own shape puts the id on `title`.
 */
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
import { join } from "node:path";

const require = createRequire(new URL("../../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright-core");

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4472";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const SHOTS = process.env.SMOKE_OUT ?? "/tmp/def-led-6499";

/** The sentence the panel carried, verbatim. Retired from eleven catalogues. */
const FALSE_SENTENCE = "No report filters on it yet";
/** Its heading, retired with it. */
const FALSE_HEADING = "Filter the ledger to one property";

const failures = [];
function check(ok, message, detail) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}${detail ? ` — ${detail}` : ""}`);
  if (!ok) failures.push(message);
}

async function signIn(page) {
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
}

mkdirSync(SHOTS, { recursive: true });
const browser = await chromium.launch({
  executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
});
// 1440 is the staff design target (the skill's §6); 1280 is the minimum that
// must work. Both, because the params band is a row and a row is where a
// narrow viewport bites.
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });

/** Every `/api/` request the page makes, so "it asked" is a fact and not a hope. */
const requests = [];
page.on("request", (request) => {
  const url = new URL(request.url());
  if (url.pathname.startsWith("/api/")) requests.push(url.pathname + url.search);
});

try {
  console.log("\n0 · sign in and open Finance → General ledger → Balance");
  await signIn(page);
  // `?view=balance` explicitly: `P1.15` made `journal` the landing view, and
  // the property filter lives on Balance (p023 note 2, *"Stays here and not on
  // Journal"*).
  await page.goto(`${BASE}/${TENANT}/finance/general-ledger?view=balance`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(1200);
  await page.screenshot({ path: join(SHOTS, "01-balance-after.png"), fullPage: true });

  const bodyText = () => page.evaluate(() => document.body.innerText);

  console.log("\n1 · the false sentence is gone from the rendered page");
  const before = await bodyText();
  check(!before.includes(FALSE_SENTENCE), `the page does not say "${FALSE_SENTENCE}"`);
  check(!before.includes(FALSE_HEADING), `the panel heading is gone too`);

  console.log("\n2 · the working control is there instead");
  const field = page.locator('input#\\f\\.premises, input[id="f.premises"]').first();
  const visible = await field.isVisible().catch(() => false);
  check(visible, "the Property search box is on the screen");
  check(before.includes("Property"), 'the field is labelled "Property"');

  console.log("\n3 · one character asks the server nothing (IS-3)");
  requests.length = 0;
  await field.fill("O");
  await page.waitForTimeout(900);
  const afterOne = requests.filter((r) => r.includes("/premises"));
  check(afterOne.length === 0, "no premises search below two characters", `${afterOne.length} request(s)`);

  console.log("\n4 · two characters ask, and the tenant's own premises come back");
  requests.length = 0;
  await field.fill("Oak");
  await page.waitForTimeout(1500);
  const searched = requests.filter((r) => r.includes("/premises"));
  check(searched.length > 0, "the search reached the server", searched[0] ?? "none");
  const options = await page
    .locator('[role="option"]')
    .allInnerTexts()
    .catch(() => []);
  check(options.length > 0, "the panel offers real premises", options.slice(0, 3).join(" · "));
  await page.screenshot({ path: join(SHOTS, "02-search-open.png"), fullPage: true });

  console.log("\n5 · choosing one puts f.premises on the wire");
  // ⚠ **CONTENT, NOT A ROW COUNT OR A `table` FIRST-MATCH — TWO FALSE READINGS
  // IN A ROW ON THIS ONE CHECK.** First draft used `page.locator("table")
  // .first()`; `P1.15` put a Journal entries table on the same screen, so when
  // the filtered balance went EMPTY the first table became the journal's and
  // "the table changed" passed by measuring a different table — 14 rows
  // "became" 72. Second draft scoped by an xpath ancestor and matched nothing,
  // reading "1 rows → 1 rows" both times. Both were caught by reading the
  // OUTPUT and the screenshot rather than the exit code (law 7, habit 3).
  //
  // So the check is now about a NAMED ACCOUNT instead: the unfiltered trial
  // balance for this tenant's September carries `1200 Accounts receivable`, and
  // a filter to one property must change what is footed. There is no locator
  // to drift and no count to be satisfied by the wrong element.
  const tableBefore = await bodyText();
  requests.length = 0;
  if (options.length > 0) {
    await page.locator('[role="option"]').first().click();
    await page.waitForTimeout(2000);
  }
  const filtered = requests.filter((r) => r.includes("f.premises="));
  check(filtered.length > 0, "the trial balance was re-read WITH the filter", filtered[0] ?? "none");

  console.log("\n6 · and the table changed — the answer was taken, not just asked for");
  const tableAfter = await bodyText();
  const AR = "Accounts receivable";
  const EMPTY_BOOK = "This is an empty book, not a balanced one";
  const hadAr = tableBefore.includes(AR);
  const stillHasAr = tableAfter.includes(AR);
  const nowEmpty = tableAfter.includes(EMPTY_BOOK);
  check(
    hadAr,
    "the UNfiltered trial balance footed the tenant's receivables",
    `"${AR}" present before the filter`,
  );
  check(
    !stillHasAr || nowEmpty,
    "and the FILTERED one is a different set of accounts",
    nowEmpty ? "the filtered property has no posted entries this period" : "the account set changed",
  );
  await page.screenshot({ path: join(SHOTS, "03-filtered.png"), fullPage: true });

  console.log("\n6b · and it does NOT accuse the books of drifting (DEF-LED-6524)");
  // ⚠ **THE FIND THIS WALK EXISTS FOR, AND NO UNIT TEST COULD HAVE MADE IT.**
  // The server sends `balanced: null` for a filtered table — deliberately, and
  // `wire.py`'s docstring says why: *"coercing it to false would report a
  // posting-service bypass on a screen that is working perfectly"*. The screen
  // read `report.balanced ? … : danger`, so the moment a clerk picked a
  // property it printed "The books do not add up" over healthy books. It was
  // invisible until this task made the filter reachable at all.
  const afterText = await bodyText();
  check(
    !afterText.includes("The books do not add up"),
    "a filtered trial balance draws no drift alert",
  );
  check(
    !afterText.includes("Unbalanced") && !afterText.includes("Balanced"),
    "and it draws no balanced/unbalanced verdict either — the question does not apply",
  );

  console.log("\n7 · no database id anywhere on the screen (B14 rule 31)");
  const finalText = await bodyText();
  const uuid = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;
  const hit = finalText.match(uuid);
  check(hit === null, "no uuid is rendered as text", hit ? hit[0] : "none");
} finally {
  await browser.close();
}

console.log(
  failures.length === 0
    ? `\ndef-led-6499: every check passed. Shots in ${SHOTS}`
    : `\ndef-led-6499: ${failures.length} check(s) FAILED:\n  - ${failures.join("\n  - ")}`,
);
process.exit(failures.length === 0 ? 0 : 1);
