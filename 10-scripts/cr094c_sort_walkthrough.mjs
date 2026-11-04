// ── Trace ──────────────────────────────────────────────
// Rules:   BR-CUS-1046 (PO 2026-09-10, EXTENDED 2026-09-12 answering
//          OQ-CUS-1790: *"(c) All eight open newest-first and the six gain a
//          sort control. Largest job: six server-side sorts."*) · NFR-3 ·
//          NFR-5 · B14 rule 13 (headers show the sort, click cycles) ·
//          B14 rule 33 (on-screen text is capped by what it is for; RATIONALE
//          is zero words on screen) · hard-won law 2 (built is not wired — and
//          its mirror, a live screen behind a dead control) · hard-won law 6
//          (no gate looks at rendered output) · PO definition of done,
//          verbatim: *"ensure you do web walkthorugh before you sign off the
//          user story or build"*
// Defects: DEF-CUS-4996 · DEF-CUS-5060 · DEF-CUS-5061
// ───────────────────────────────────────────────────────
//
// WHAT THIS OPENS, AND WHY EACH ONE NEEDS A BROWSER.
//
//   1 · **The default, on screen.** The test suite asserts `defaultSort` in a
//       config object and the backend suite asserts an `ORDER BY` on a
//       queryset. Neither can say that the row a clerk sees first is the row
//       created last. This reads the first cell of the rendered table.
//   2 · **The footnote sentences.** Four of them claimed an ordering that the
//       ruling removes, and a comment claiming a guarantee is not the guarantee
//       (law 1). Only rendered text can say what a clerk actually reads, and
//       only a browser can confirm the catalogue answered rather than printing
//       the KEY — which is what a missing key does, silently.
//   3 · **The sort control, PRESSED.** `sortable: true` renders a button;
//       carrying `sort` to the server is a different half. This clicks a header
//       and checks THREE things at once: the URL gains the parameter, the arrow
//       appears, and the ROWS MOVE. A live control over a fixed order passes
//       the first two and fails the third, and that is exactly the shape law 2
//       is about.
//   4 · **Both widths.** The skill's staff-app pair is 1280 and 1440.
//
// ⚠ **WHAT IT CANNOT SEE, SAID OUT LOUD RATHER THAN IMPLIED (law 7).** The
// demo utility holds ONE move-in, ONE move-out, ZERO transfers and six
// disconnects, so on those four tabs there is no POSITION to read: every
// ordering puts the same row first. This script reports the row count it found
// per tab and only claims an ordering where it could see one. Those four are
// ordered by the one shared `order_terms` helper and asserted against the
// queryset's own `ORDER BY` in
// `06-backend/tests/test_br_cus_1046_lists_open_newest_first.py`.
// `10-scripts/cr094c_seed_worklist_rows.py` says why they are not seeded.
import { existsSync, readdirSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

// ⚠ **CHECK THE PORT IS YOURS BEFORE YOU BELIEVE A WORD OF THE OUTPUT.** A
// sibling lane already serving this port means every request goes to their tree
// and their database, and the run still answers 200 and draws a real screen.
const BASE = process.env.BASE ?? "http://127.0.0.1:8641";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr094c";
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
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
  throw new Error("no chromium found");
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const say = (...parts) => console.log(...parts);
let failures = 0;
const check = (ok, what) => {
  say(`${ok ? "  ok  " : "  FAIL"} ${what}`);
  if (!ok) failures += 1;
};

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
say(`signed in as ${EMAIL} on ${TENANT} at 1440×1000\n`);

const openTab = async (tab) => {
  await page.goto(`${BASE}/${TENANT}/accounts?tab=${tab}`, { waitUntil: "networkidle" });
  await page.waitForSelector("h1", { timeout: 30000 });
  await page.waitForTimeout(700);
};

/** The first cell of every body row, in render order. */
const firstCells = () =>
  page.$$eval("table.data-table tbody tr", (rows) =>
    rows.map((row) => (row.querySelector("td")?.innerText ?? "").trim()).filter((t) => t !== ""),
  );

const bodyText = () => page.evaluate(() => document.body.innerText);

// ══ 1 · ACCOUNTS — THE DEFECT STEP 1 MEASURED, READ OFF THE SCREEN ════════
say("── 1 · Accounts (DEF-CUS-4996) · the newest account was at position 58 of 73");
await openTab("accounts");
let cells = await firstCells();
say(`   rows drawn: ${cells.length} · first three: ${cells.slice(0, 3).join(" · ")}`);
// ⚠ **`startsWith`, NOT `===`, AND THE FIRST DRAFT GOT THIS WRONG.** The cell
// renders the account number AND its `Master` kind chip (`BR-CUS-068`), so the
// innerText is `AC-2026-00052 Master`. An equality check reported a FAIL over a
// correctly ordered list — a false finding, which is the thing a walkthrough
// exists to avoid rather than manufacture.
check(
  (cells[0] ?? "").startsWith("AC-2026-00052"),
  `the newest account is row ONE (got ${cells[0] ?? "nothing"})`,
);

// …and the clerk's own sort still wins, which is the ruling's second clause.
const nameHeader = page.locator("th button.table-sort", { hasText: /^Name$/ });
await nameHeader.click();
await page.waitForTimeout(900);
const sortedByName = await firstCells();
check(page.url().includes("sort=name"), `clicking NAME puts it in the URL (${page.url().split("?")[1] ?? ""})`);
check(
  sortedByName[0] !== cells[0],
  `…and the ROWS MOVE (${cells[0]} → ${sortedByName[0]}) — a live control over a fixed order would not`,
);
const arrow = await page.$$eval("th .table-sort-arrow", (els) => els.map((e) => e.textContent));
check(arrow.length === 1, `exactly one header carries the arrow (B14 rule 13) — saw ${arrow.length}`);

// A refresh must keep it: `BR-CUS-1046` clause 2 in as many words.
await page.reload({ waitUntil: "networkidle" });
await page.waitForTimeout(900);
check(
  (await firstCells())[0] === sortedByName[0],
  "the chosen sort SURVIVES A REFRESH — the rule's own second clause",
);

// ══ 2 · REQUESTS — the one sibling tab with enough rows to see an order ═══
say("\n── 2 · Requests (DEF-CUS-5060) · opened on `received_at` ASC until today");
await openTab("requests");
cells = await firstCells();
say(`   rows drawn: ${cells.length} · first three: ${cells.slice(0, 3).join(" · ")}`);
check(
  (cells[0] ?? "").startsWith("SR-CR094-01"),
  `the newest request is row ONE (got ${cells[0] ?? "nothing"})`,
);
let text = await bodyText();
check(
  text.includes("Opens newest first."),
  "the footnote states the ordering in the tenant's own language",
);
check(
  !text.includes("oldest thing waiting is the thing"),
  "…and the RATIONALE that claimed the old ordering is gone (law 1, B14 rule 33)",
);
check(
  !text.includes("customers.serviceRequest.list.sortFootnote"),
  "…and the catalogue answered rather than printing the KEY",
);

// The urgency ordering is not lost — it is one click. That is what made option
// (c) available to the PO at all.
const receivedHeader = page.locator("th button.table-sort", { hasText: /^Received$/ });
await receivedHeader.click();
await page.waitForTimeout(900);
const byReceived = await firstCells();

// ⚠ **A PROPERTY, NOT A ROW NAME — AND THREE DRAFTS NAMED A ROW AND ALL THREE
// WERE WRONG.** They asserted a specific `SR-CR094-…` reference, which depends
// on how the seeder happens to relate to the six requests `sample_data` already
// wrote: the genuinely oldest RECEIVED request on this utility is `SR-26-0001`
// (2026-08-28), older than anything the seeder plants. Each draft reported a
// FAIL over an ordering that was correct in both directions — a false finding,
// three times, from a check that knew a row rather than a rule.
//
// So this asks two questions neither seeding nor the demo data can break: did
// the ORDER change when the heading was pressed, and does the SCREEN render
// what the SERVER ordered?
const apiByReceived = await page.evaluate(async (tenant) => {
  const res = await fetch(
    `/api/${tenant}/service-requests?segment=open&sort=received_at&dir=asc&per=50`,
    { credentials: "include" },
  );
  const body = await res.json();
  const dates = body.results.map((row) => row.received_at);
  return {
    first: body.results[0]?.request_no,
    ordered: JSON.stringify(dates) === JSON.stringify([...dates].sort()),
    sorts: body.sorts,
  };
}, TENANT);
check(
  byReceived[0] !== cells[0],
  `clicking RECEIVED re-orders the list (${cells[0]} → ${byReceived[0]}) — the ordering this tab lost`,
);
check(
  apiByReceived.ordered,
  "…and the server really orders by received_at ascending, end to end",
);
check(
  (byReceived[0] ?? "").startsWith(apiByReceived.first ?? "\u0000"),
  `…and the SCREEN renders what the SERVER ordered (server says ${apiByReceived.first})`,
);
// BR-SHL-010 — the screen may only offer a sort the server declares, so the
// served vocabulary is READ rather than assumed. This also catches the trap that
// cost this lane two false findings: a STALE `runserver` process serving the
// previous module, which answers 200 and draws a real screen the whole time.
check(
  (apiByReceived.sorts ?? []).includes("received_at"),
  `the server declares the sort the heading offers (served: ${(apiByReceived.sorts ?? []).join(", ")})`,
);

// ⚠ **AND HERE IS THE ONE THING THIS WAVE DID NOT FIX, MEASURED RATHER THAN
// ASSUMED — `DEF-CUS-5091`.** `BR-CUS-1046`'s second clause is *"a clerk's
// chosen sort must still win and still survive a refresh"*. It WINS on all
// eight tabs: the parameter reaches the server, the `ORDER BY` changes and the
// rows move, which the check above just proved. It SURVIVES A REFRESH only on
// the accounts tab, which is the only one of the eight that keeps its table
// state in the query string (`useSearchParams`). The seven sibling tabs hold it
// in `useState`, deliberately and for a reason that predates this ruling:
// `DEF-664` gave the embedded Requests list `urlState={false}` because all
// eight tabs share ONE query string and each one's `?sort=` would overwrite the
// others'. Fixing it means namespacing the parameters per tab, which changes
// every one of them at once — so it is FILED rather than decided here.
//
// This assertion states the CURRENT truth. When `DEF-CUS-5091` is fixed it goes
// red and names itself, which is the only kind of note that does not rot.
const sortInUrl = page.url().includes("sort=received_at");
check(
  !sortInUrl,
  "the embedded Requests tab keeps its sort OUT of the URL (DEF-664's design, " +
    "and DEF-CUS-5091 is the clause it costs) — flip this check when 5091 lands",
);

// ══ 3 · THE OTHER FIVE TABS — what is drawn, and what could not be seen ═══
say("\n── 3 · the remaining five tabs · rows found, and the sentence each prints");
for (const [tab, sentence] of [
  ["new-connects", "Opens newest first."],
  ["move-ins", "Opens newest first."],
  ["move-outs", "Opens newest first."],
  ["transfers", "Opens newest first."],
  ["disconnects", "Opens newest first."],
]) {
  await openTab(tab);
  const rows = await firstCells();
  const body = await bodyText();
  const seen = body.includes(sentence);
  const stale = /soonest first|oldest first —|Sorted by account number|Newest job first —/.test(body);
  say(
    `   ${tab.padEnd(13)} rows=${String(rows.length).padEnd(3)} ` +
      `footnote=${seen ? "yes" : "NO"} stale-sentence=${stale ? "YES" : "no"}` +
      (rows.length < 2 ? "   (too few rows to read a POSITION — stated, not claimed)" : ""),
  );
  if (rows.length === 0 && tab === "transfers") {
    // The one genuine empty state on this screen. A footnote under an empty
    // table is not owed and its absence is not a finding.
    check(!stale, `${tab}: no superseded sentence on an empty tab`);
    continue;
  }
  check(seen, `${tab}: the new footnote is rendered`);
  check(!stale, `${tab}: no superseded ordering sentence is left on screen`);
}

// ══ 4 · IMPORTS — the cap is off the server (DEF-CUS-5061) ════════════════
say("\n── 4 · Imports (DEF-CUS-5061) · the 200-row cap and the missing count");
const envelope = await page.evaluate(async (tenant) => {
  const res = await fetch(`/api/${tenant}/imports?f.target=accounts`, { credentials: "include" });
  const body = await res.json();
  return { keys: Object.keys(body).sort(), total: body.total, rows: (body.rows ?? []).length };
}, TENANT);
say(`   envelope keys: ${envelope.keys.join(", ")}`);
check(
  envelope.keys.includes("total"),
  `the response carries a count (total=${envelope.total}) — it carried none`,
);
check(envelope.keys.includes("pages"), "…and a page count, so a pager can be honest");
await openTab("imports");
check((await firstCells()).length > 0, "the Imports tab still draws its runs");

// ══ 5 · 1280 — the other half of the staff-app pair ═══════════════════════
say("\n── 5 · the same screen at 1280 (the laptop minimum)");
await page.setViewportSize({ width: 1280, height: 900 });
await openTab("accounts");
cells = await firstCells();
check((cells[0] ?? "").startsWith("AC-2026-00052"), "1280: the newest account is still row one");
const overflow = await page.evaluate(
  () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
);
check(!overflow, "1280: the page body does not scroll sideways");
await page.screenshot({ path: `${OUT}/accounts-1280.png`, fullPage: false });
await page.setViewportSize({ width: 1440, height: 1000 });
await openTab("requests");
await page.screenshot({ path: `${OUT}/requests-1440.png`, fullPage: false });
say(`   screenshots in ${OUT}`);

say(`\n${failures === 0 ? "ALL CHECKS PASSED" : `${failures} CHECK(S) FAILED`}`);
await browser.close();
process.exit(failures === 0 ? 0 : 1);
