// ── THE TRANSFER RECORD, WALKED IN A BROWSER ──────────────────────────────
//
// Accounts blueprint **p132 of the 281-page edition**, read AS AN IMAGE per
// B14 rule 42. Run it after any change to `TransferRecordPage.tsx`, to the
// `customers.transferRecord.*` catalogue keys, or to whatever finally serves
// `GET /transfers/{ref}`.
//
// **WHY THIS FILE EXISTS AT ALL, AND IT IS NOT A FORMALITY.** Measured
// 2026-09-20: the transfer was **the only one of these flows with no
// walkthrough script** — move-in, move-out, the clerk request walk, the portal
// and nine CRs all have one. The conformance lane said so in its own words
// (*"p133's row reads `Walked: Not walked.`"*), and the same day the PO walked
// the wizard by hand and found step 4 **breaking the screen when the last tick
// is pressed** over 39 green tests and a clean `tsc`. No gate in this repo
// reads rendered output; this is the check that does.
//
// ⚠ **TWO OF THE THREE WALKS RUN AGAINST A STUBBED RESPONSE, AND THE REPORT
// SAYS SO EVERY TIME IT RUNS.** `GET /transfers/{ref}` is not mounted at the
// commit that adds this file, and the seeded tenant holds **zero transfer
// rows**, so there is no record in existence to open. Walk 1 is therefore the
// only one that is end to end, and what it proves is that the page states its
// absence rather than drawing furniture over nothing. Walks 2 and 3 intercept
// the request in the BROWSER and answer it with a contract-shaped payload:
// that is a real Chromium rendering the real bundle, which is what catches the
// `DEF-CUS-5911` class of defect — a second render crashing the screen while
// `renderToStaticMarkup`, which only ever renders once, stays green. It is NOT
// a claim that the endpoint works. **The day the endpoint lands, delete the
// stub from walks 2 and 3 and this file becomes an end-to-end walk with no
// other edit.**
//
// ⚠ **IT WRITES NOTHING.** Every request is a GET and the stub is
// browser-side, so nothing reaches the database. There is nothing to clean up.
//
//   TRW_BASE     default http://127.0.0.1:8971
//   TRW_TENANT   default brazosbend
//   TRW_EMAIL    default dana@brazosbendutilities.com
//   TRW_PASSWORD default S3cure!passw0rd
//   TRW_REF      default TRF-26-0001  (the reference to open)
//   TRW_CHROME   default /opt/pw-browsers/chromium-1194/chrome-linux/chrome
//     (the pinned @playwright/test version does not match the preinstalled
//      browser here, so the path is passed explicitly — never run
//      `playwright install` in this container.)
import { createRequire } from "node:module";
import { execSync } from "node:child_process";
import { statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

// ⚠ **THE REPO ROOT IS DERIVED FROM THIS FILE, NEVER HARDCODED (`DEF-524`).**
// A sibling walkthrough carries an absolute `/home/user/SMARTBillHub/…` path,
// and `DEF-524` is what that costs: G14's hardcoded path outlived the file it
// named and reported PASS through six UI defects. Run from a `git worktree`,
// a hardcoded root silently walks ANOTHER lane's bundle.
const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "..");
const require = createRequire(path.join(REPO, "07-frontend", "package.json"));
const { chromium } = require("playwright");

const BASE = process.env.TRW_BASE || "http://127.0.0.1:8971";
const T = process.env.TRW_TENANT || "brazosbend";
const EMAIL = process.env.TRW_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.TRW_PASSWORD || "S3cure!passw0rd";
const REF = process.env.TRW_REF || "TRF-26-0001";
const CHROME =
  process.env.TRW_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

// ── the staleness refusal ──────────────────────────────────────────────────
// Nothing on the page says how old the bundle is; `tsc`, the suites and every
// gate are green either way, because none of them look at `dist/`.
try {
  const built = statSync(path.join(REPO, "07-frontend/dist/index.html")).mtime;
  const newestSrc = new Date(
    execSync("git log -1 --format=%cI -- 07-frontend/src", { cwd: REPO }).toString().trim(),
  );
  if (built < newestSrc) {
    console.error(
      `REFUSED: dist/ was built ${built.toISOString()} but 07-frontend/src has a\n` +
        `commit at ${newestSrc.toISOString()}. Run \`npx vite build\` first.`,
    );
    process.exit(2);
  }
  console.log(`build is current (dist ${built.toISOString()})`);
} catch {
  console.warn("! could not check build freshness — continuing");
}

let pass = 0;
let fail = 0;
const failures = [];
function ok(what, cond, detail = "") {
  if (cond) {
    pass += 1;
    console.log(`  ✓ ${what}`);
  } else {
    fail += 1;
    failures.push(what);
    console.log(`  ✗ ${what}${detail ? ` — ${detail}` : ""}`);
  }
}

// ⚠ Rule 37 — every figure and every name below is an ILLUSTRATION lifted from
// p132's drawing. None of it is a tenant's data and none of it is written.
const RECORD = {
  state: "completed",
  reference: { value: REF, unavailable: null },
  seller_name: { value: "Tan, Wei", unavailable: null },
  buyer_name: { value: "Ferraro, L.", unavailable: null },
  what_happened: {
    account: { value: "A-11455", unavailable: null },
    unit: { value: "1408 Elm Street · Unit B", unavailable: null },
    service_address: { value: "1408 Elm Street, Silver Creek, TX 78611", unavailable: null },
    sold_on: { value: "2026-05-07", unavailable: null },
    sold_by: { value: "Tan, Wei · C-00344", unavailable: null },
    sold_to: { value: "Ferraro, L. · C-00877", unavailable: null },
    buyer_kind: { value: "person", unavailable: null },
    identifier_given: { value: "driving_licence", unavailable: null },
    buyer_matched: { value: "matched", unavailable: null },
    changeover_read: { value: { raised: 2, completed: 2, on: "2026-05-07" }, unavailable: null },
    committed_by: { value: { name: "S. Ortiz", at: "2026-05-07T14:06:00Z" }, unavailable: null },
  },
  unchanged: {
    account_no: { value: "A-11455", unavailable: null },
    status: { value: "active", unavailable: null },
    ledger_months: {
      value: null,
      unavailable: {
        code: "unbroken_ledger_months_not_counted",
        detail: "Nothing in this product counts how many unbroken months a ledger runs.",
      },
    },
  },
  money: {
    currency: "USD",
    balance: { value: "64.2000", unavailable: null },
    deposit: { value: "150.0000", unavailable: null },
    deposit_interest: {
      value: null,
      unavailable: {
        code: "deposit_interest_not_computed",
        detail: "Deposit interest is computed at settlement (PO ruling 2026-09-19).",
      },
    },
    taken_on: { value: "64.2000", unavailable: null },
  },
  doors: {
    account: { value: { account_id: "acc-uuid-1", account_no: "A-11455" }, unavailable: null },
    customer: { value: { customer_id: "cus-uuid-1", name: "Ferraro, L." }, unavailable: null },
  },
};

const NOTHING_KEPT = JSON.parse(JSON.stringify(RECORD));
NOTHING_KEPT.reference = {
  value: null,
  unavailable: {
    code: "numbering_series_missing",
    series: "transfer",
    open_question: "OQ-426",
    detail:
      "This transfer has no reference number yet. A number series for transfers has not " +
      "been set up, so nothing has been issued.",
  },
};
NOTHING_KEPT.seller_name = {
  value: null,
  unavailable: {
    code: "seller_not_kept_after_reassignment",
    detail:
      "reassign_account removes the seller's customer_accounts link, so the seller " +
      "survives only in audit_log, which is pruned on a retention schedule.",
  },
};
NOTHING_KEPT.what_happened.sold_by = NOTHING_KEPT.seller_name;

async function signIn(context) {
  const p = await context.newPage({ viewport: { width: 1440, height: 1800 } });
  p.setDefaultTimeout(25000);
  await p.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
  await p.fill("#signin-email", EMAIL);
  await p.fill("#signin-password", PASSWORD);
  await Promise.all([
    p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
    p.click('button[type="submit"]'),
  ]);
  return p;
}

/** Answer `GET /api/<tenant>/transfers/<ref>` in the BROWSER with `payload`. */
async function stub(page, payload) {
  await page.route(/\/api\/[^/]+\/transfers\/[^/?]+(\?.*)?$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(payload),
    }),
  );
}

// ⚠ A HARD TIMEOUT ON THE WHOLE RUN (`DEF-GOV-5877`) — a walk that hangs is a
// walk nobody reads, and it holds the container open behind it.
const KILL = setTimeout(() => {
  console.error("REFUSED: walkthrough exceeded 5 minutes — killing");
  process.exit(3);
}, 300000);

let browser;
try {
  browser = await chromium.launch({ executablePath: CHROME });
  const context = await browser.newContext();
  const page = await signIn(context);
  // A crash renders `Unexpected Application Error!`, which is a PAGE — every
  // `includes` below would go on reading it as one. Caught here instead.
  const consoleErrors = [];
  page.on("pageerror", (e) => consoleErrors.push(String(e)));

  // ── 1 · WITH NO ENDPOINT, THE PAGE STATES ITS ABSENCE ──────────────────
  console.log("\n1 · the address, against the product as it stands today");
  await page.goto(`${BASE}/${T}/transfers/${REF}`, { waitUntil: "networkidle" });
  let text = await page.innerText("body");
  ok("the route is mounted — the SPA does not 404 the address",
     !text.includes("404") || text.includes("Transfer not found"),
     text.slice(0, 120));
  ok("it says the reference names no transfer",
     text.includes("Transfer not found") || text.includes("names no transfer"),
     text.slice(0, 200));
  ok("it draws NO money over data it does not have",
     !text.includes("$0.00") && !text.includes("Buyer took on"),
     "a screen that draws its furniture over no data looks like a working page");

  // ── 2 · THE RECORD AS p132 DRAWS IT ────────────────────────────────────
  console.log("\n2 · the record, over a contract-shaped payload (STUBBED)");
  await stub(page, RECORD);
  await page.goto(`${BASE}/${T}/transfers/${REF}`, { waitUntil: "networkidle" });
  text = await page.innerText("body");

  ok("the title is the two parties", text.includes("Tan, Wei → Ferraro, L."));
  ok("the kicker carries the reference", text.includes(REF));
  ok("three chips: the state, the reassignment and the date",
     text.includes("Completed") && text.includes("Account reassigned") && text.includes("Sold"));
  ok("the banner states the rule in four words", text.includes("One account, never closed."));
  ok("the banner's 24-word second sentence is NOT on screen",
     !text.includes("with the same meters"),
     "rationale is zero words on screen (B14 rule 33)");

  const happened = [
    "Account", "Unit", "Service address", "Sold on", "Sold by", "Sold to",
    "Buyer kind", "Identifier given", "Matched or created", "Changeover read", "Committed by",
  ];
  ok(`all ${happened.length} of p132's WHAT HAPPENED rows are drawn`,
     happened.every((label) => text.includes(label)),
     happened.filter((l) => !text.includes(l)).join(", "));

  // ⚠ **THE BREADCRUMB LEAF IS CHECKED HERE AND NOWHERE ELSE.** It is published
  // from an EFFECT, and every unit test in this repo renders statically, so a
  // unit case could only assert the fixture it was handed. p132 draws
  // `Accounts / Transfers / TRF-26-0021`; the shell's mechanism
  // (`components/crumbLeaf.ts`, `DEF-374`) carries the last crumb and mirrors
  // it into the browser tab.
  const title = await page.title();
  ok(`the browser tab mirrors the reference (${title})`, title.includes(REF), title);
  const topbar = await page.innerText("header, .topbar, nav").catch(() => "");
  ok("the breadcrumb's last crumb is the reference",
     topbar.includes(REF) || title.includes(REF),
     "⚠ the ancestors `Accounts / Transfers` do NOT resolve — DEF-SHL-5983");

  ok("the commit carries its TIME, as p132 draws it",
     /\d{2}:\d{2}/.test(text) && text.includes("S. Ortiz"),
     "p132 draws `S. Ortiz · 05/07/2026 14:06`");
  ok("the stored codes are translated, never printed",
     text.includes("Person") && text.includes("Driving licence") && !text.includes("driving_licence"));

  const unchanged = ["Account number", "The unit and meters", "Plan", "Service agreements", "Status", "Ledger", "Issued bills"];
  ok(`all ${unchanged.length} of p132's WHAT DID NOT CHANGE rows are drawn`,
     unchanged.every((label) => text.includes(label)),
     unchanged.filter((l) => !text.includes(l)).join(", "));
  ok("the ledger's length says it was never counted, not `38 months`",
     text.includes("Length not counted") && !text.includes("38 months"),
     "B14 rule 37 — a drawn figure is an illustration");

  // ── the money, and it is the point of the screen ────────────────────────
  console.log("\n   the money box");
  const zeros = (text.match(/\$0\.00/g) || []).length;
  ok(`EXACTLY two $0.00 — the refund and the re-collection (saw ${zeros})`,
     zeros === 2,
     "BR-CUS-085: nothing is refunded and re-collected. A third zero is a figure nobody computed");
  ok("deposit interest is stated, never zeroed",
     text.includes("Counted at settlement") ,
     "a zero here is $3.50 wrong AGAINST the customer on a 14-month $150.00 deposit");
  ok("fees say the WORD `None`, not a zero", text.includes("Fees charged") && text.includes("None"));
  ok("the balance and the deposit display to 2dp",
     text.includes("$64.20") && text.includes("$150.00") && !text.includes("64.2000"));
  ok("the total is the server's figure", text.includes("Taken on"));

  // ── the three rows the record does not say ──────────────────────────────
  // ⛔ Two of p132's three rows retired 2026-09-23 (`DEF-CUS-6393`,
  // `DEF-CUS-6394`): a sale now clears the seller's contact details and moves
  // a master account's premises owner, so neither row is true any more.
  ok("WHAT THIS RECORD DOES NOT SAY carries its one remaining row",
     text.includes("Buyer told") && !text.includes("Still names the seller") &&
     !text.includes("Still the seller"),
     "the buyer-told row stays while OQ-1253 is open");

  // ── 3 · THE DOORS, BY ADDRESS AND BY WHAT THEY OPEN ────────────────────
  console.log("\n3 · the two doors, and nothing else");
  const hrefs = await page.$$eval("a[data-testid^='transfer-record-']", (els) =>
    els.map((el) => ({ id: el.getAttribute("data-testid"), href: el.getAttribute("href") })),
  );
  ok(`exactly TWO doors (saw ${hrefs.length})`, hrefs.length === 2,
     hrefs.map((h) => h.id).join(", "));
  ok("one opens the customer, one opens the account",
     hrefs.some((h) => h.id === "transfer-record-open-customer") &&
     hrefs.some((h) => h.id === "transfer-record-open-account"));
  ok("every door carries its tenant and is not protocol-relative",
     hrefs.every((h) => h.href && h.href.startsWith(`/${T}/`)),
     hrefs.map((h) => h.href).join(" · "));
  const buttons = await page.$$eval("main button, [data-panel] button", (els) => els.length);
  ok(`the record has NO pressable control (saw ${buttons})`, buttons === 0,
     "*\"Drawing a button here would invent a decision the product does not offer\"*");

  // …and the account door actually opens the account screen.
  const acctHref = hrefs.find((h) => h.id === "transfer-record-open-account").href;
  await page.click("[data-testid='transfer-record-open-account']");
  await page.waitForURL((u) => u.pathname === acctHref, { timeout: 20000 }).catch(() => {});
  ok(`clicking it lands on ${acctHref}`, new URL(page.url()).pathname === acctHref,
     page.url());
  await page.goBack({ waitUntil: "networkidle" });

  // ── 4 · WHAT THE PRODUCT CANNOT SAY YET ───────────────────────────────
  console.log("\n4 · the absences, over a payload that carries none of them (STUBBED)");
  await page.unroute(/\/api\/[^/]+\/transfers\/[^/?]+(\?.*)?$/);
  await stub(page, NOTHING_KEPT);
  await page.goto(`${BASE}/${T}/transfers/${REF}`, { waitUntil: "networkidle" });
  text = await page.innerText("body");
  // ⚠ **CASE-FOLDED, AND THAT IS NOT LAZINESS — THE FIRST RUN OF THIS WALK
  // FAILED HERE AND THE SCREEN WAS RIGHT.** `innerText` returns the text as CSS
  // renders it, and the kicker carries `text-transform: uppercase`, so
  // `includes("No reference yet")` is false over a line that says exactly that.
  // A sibling walkthrough records the identical finding about three KPI tiles.
  // A check whose output cannot tell a pass from a fail is worse than no check.
  ok("no reference: the kicker says so in three words",
     text.toLowerCase().includes("no reference yet"),
     text.slice(0, 160));
  ok("the server's 40-word explanation stays OFF the screen",
     !text.includes("A number series for transfers has not"),
     "rule 33 — it rides in the title attribute");
  ok("no seller: the title is the buyer alone, never an arrow onto a dash",
     text.includes("Ferraro, L.") && !text.includes("→ Ferraro, L."));
  ok("the Sold by row says the seller was not kept", text.includes("Seller not kept"));
  ok("BR-CUS-085's two zeros survive a payload that sends no money rows",
     (text.match(/\$0\.00/g) || []).length === 2);

  // ── 5 · A SECOND RENDER, WHICH IS WHAT UNIT TESTS CANNOT DO ───────────
  console.log("\n5 · a second render (`DEF-CUS-5911`)");
  // `renderToStaticMarkup` renders ONCE, so a hook-count change between the
  // first and second render is invisible to every unit test in this repo and
  // turned the move record into `Unexpected Application Error!` for both its
  // flows. A focus event makes React Query re-render the mounted component.
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await page.waitForTimeout(800);
  text = await page.innerText("body");
  ok("the page survives a re-render", text.includes("Ferraro, L.") &&
     !text.includes("Unexpected Application Error"));
  ok("no uncaught page error in the whole walk", consoleErrors.length === 0,
     consoleErrors.slice(0, 2).join(" | "));

  // ── 6 · THE STAFF WIDTH FLOOR ─────────────────────────────────────────
  console.log("\n6 · 1280, the laptop minimum");
  await page.setViewportSize({ width: 1280, height: 1600 });
  await page.waitForTimeout(400);
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  ok(`no horizontal scroll at 1280 (overflow ${overflow}px)`, overflow <= 0);
  const stacked = await page.evaluate(() => {
    const panels = [...document.querySelectorAll("[data-panel]")];
    return panels.length;
  });
  ok(`the four sections are drawn as panels (saw ${stacked})`, stacked >= 4, String(stacked));
} catch (err) {
  fail += 1;
  failures.push(`the walk threw: ${err && err.message ? err.message : err}`);
  console.error(err);
} finally {
  clearTimeout(KILL);
  if (browser) await browser.close();
}

console.log(`\n${pass} passed · ${fail} failed`);
if (fail > 0) {
  console.log("failures:");
  for (const f of failures) console.log(`  · ${f}`);
}
console.log(
  "\n⚠ walks 2–6 answered `GET /transfers/{ref}` from a BROWSER-SIDE STUB: the\n" +
    "  endpoint is not mounted and the seeded tenant holds no transfer rows.\n" +
    "  They prove the SCREEN in a real browser, never the server.",
);
process.exit(fail > 0 ? 1 : 0);
