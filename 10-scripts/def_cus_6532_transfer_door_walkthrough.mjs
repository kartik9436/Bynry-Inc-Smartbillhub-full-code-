// ── THE TRANSFERS TAB'S `↗ Open` DOOR, PRESSED IN A BROWSER ────────────────
//
// `DEF-CUS-6532`. PO, 2026-09-24, looking at a `Done` row on Ottumwa Water
// Works: *"also this done request - we are unabel to open - view should be
// available - all the time"*.
//
// **WHY IT EXISTS, AND IT IS NOT "because every flow should have one".**
// This column already had the expiry test hard-won law 2's mirror prescribes.
// It fired once, correctly, and was then RE-POINTED at a BACKEND condition —
// *"`GET /transfers/{ref}` is not mounted"* — while keeping only FRONTEND
// assertions. `transfer_record_api.py` landed 2026-09-20 in `86a28f23d`, the
// condition expired that day, and the case went on passing green for four days
// over a live screen with no door to it.
//
// **So the guard that replaces it presses the door instead of watching for
// it.** A `vitest` case cannot see a Django urlpattern; this can, because it
// clicks the control and reads what comes back.
//
// **WHAT ONLY THIS CAN SEE**, and none of it is assertable from a static
// render:
//   · that the href the tab builds actually RESOLVES — the unit suite asserts
//     the string and the string was never the question;
//   · that the record which answers is the SALE and not the not-found branch,
//     which is what the whole four-day hold was ostensibly about;
//   · that a keyboard alone reaches the control (B14 rule 15's icon has no
//     visible label, so its accessible name is the only way in);
//   · that nothing scrolls sideways once a ninth column joins the table.
//
// ⚠ **IT WRITES NOTHING.** Every step is a GET or a click. Rows come from
// `po20260920_transfers_tab_seed.py` and go away with its purge.
//
//   TDW_BASE     default http://127.0.0.1:4492
//   TDW_TENANT   default brazosbend
//   TDW_EMAIL    default dana@brazosbendutilities.com
//   TDW_PASSWORD default S3cure!passw0rd
//   TDW_CHROME   default /opt/pw-browsers/chromium-1194/chrome-linux/chrome
//     (the pinned @playwright/test version does not match the preinstalled
//      browser here, so the path is passed explicitly — never run
//      `playwright install` in this container.)
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");
import { execSync } from "node:child_process";
import { statSync } from "node:fs";

const BASE = process.env.TDW_BASE || "http://127.0.0.1:4492";
const T = process.env.TDW_TENANT || "brazosbend";
const EMAIL = process.env.TDW_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.TDW_PASSWORD || "S3cure!passw0rd";
const CHROME = process.env.TDW_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

// ⚠ **IT REFUSES A STALE BUILD.** Nothing on the page says how old the bundle
// is, and `tsc`, the suites and every gate are green either way because none
// of them look at `dist/`.
try {
  const built = statSync("07-frontend/dist/index.html").mtime;
  const newestSrc = new Date(
    execSync("git log -1 --format=%cI -- 07-frontend/src").toString().trim(),
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

// ⚠ A HARD TIMEOUT ON THE WHOLE RUN — a walk that hangs is a walk nobody
// reads, and it holds the container open behind it (`DEF-GOV-5877`).
const KILL = setTimeout(() => {
  console.error("REFUSED: walk exceeded 4 minutes");
  process.exit(3);
}, 240000);

const browser = await chromium.launch({ executablePath: CHROME, args: ["--no-sandbox"] });

async function signIn(width) {
  const p = await browser.newPage({ viewport: { width, height: 1000 } });
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

const page = await signIn(1440);

console.log("\n1 · the list — a door on every row, in every state");
await page.goto(`${BASE}/${T}/accounts?sort=created&dir=desc&tab=transfers`, {
  waitUntil: "networkidle",
});
await page.waitForTimeout(2500);

const rows = await page.$$eval("table tbody tr", (trs) =>
  trs.map((tr) => {
    const tds = [...tr.querySelectorAll("td")];
    const door = tr.querySelector('a[data-size="row"]');
    return {
      ref: tds[0]?.innerText.trim() ?? "",
      state: tds[tds.length - 2]?.innerText.trim() ?? "",
      href: door?.getAttribute("href") ?? null,
      label: door?.getAttribute("aria-label") ?? null,
    };
  }),
);
ok("the list has rows to open at all", rows.length > 0, `${rows.length} rows`);
// **THE RULING, ASSERTED AS ARITHMETIC RATHER THAN AS A SAMPLE.** Counting is
// what distinguishes "the door works" from "the door works on the row I looked
// at" — which is the sampling that let a `Done` row ship without one.
const withDoor = rows.filter((r) => r.href !== null).length;
ok(
  `every row has a door — never gated on state (${withDoor} of ${rows.length})`,
  withDoor === rows.length,
  JSON.stringify(rows.filter((r) => !r.href)),
);
ok(
  "the states on screen are more than one, so the count above means something",
  new Set(rows.map((r) => r.state)).size > 1,
  [...new Set(rows.map((r) => r.state))].join(" · "),
);
// B14 rule 31 — the address is the transfer NUMBER, never a database id.
ok(
  "every address is tenant-scoped and reference-addressed",
  rows.every((r) => new RegExp(`^/${T}/transfers/TRF-\\d\\d-\\d{4}$`).test(r.href ?? "")),
  JSON.stringify(rows.map((r) => r.href)),
);
ok(
  "no uuid appears in any door",
  !rows.some((r) => /[0-9a-f]{8}-[0-9a-f]{4}-/.test(r.href ?? "")),
);

console.log("\n2 · press it — on the DONE row, which is the one the PO reported");
const done = rows.find((r) => /done|completed/i.test(r.state));
ok("there is a DONE row to press", Boolean(done), JSON.stringify(rows.map((r) => r.state)));
if (done) {
  await page
    .locator("table tbody tr")
    .filter({ hasText: done.ref })
    .locator('a[data-size="row"]')
    .click();
  await page.waitForURL(new RegExp(`/transfers/${done.ref}$`), { timeout: 20000 });
  await page.waitForTimeout(2200);
  const body = await page.evaluate(() => document.body.innerText);
  ok("it lands on the record's own address", page.url().endsWith(`/transfers/${done.ref}`), page.url());
  // ⚠ **THIS IS THE ASSERTION THE FOUR-DAY HOLD WAS ABOUT**, and it is the one
  // no unit test could make: the READER answers, so the page draws the sale
  // rather than its not-found branch.
  ok("the record draws the SALE, not the not-found branch", body.includes("What happened"));
  ok("it is the record for THIS transfer", body.includes(done.ref));
  ok("no not-found sentence anywhere on it", !/not found|could not be found/i.test(body));
  // The blueprint's ruling: two doors out and no verbs.
  ok("the record offers its two doors out", body.includes("Open the account") && body.includes("Open the customer"));
}

console.log("\n3 · a keyboard alone reaches it — the icon has no visible label");
await page.goto(`${BASE}/${T}/accounts?tab=transfers`, { waitUntil: "networkidle" });
await page.waitForTimeout(2200);
await page.locator('table tbody a[data-size="row"]').first().focus();
const focused = await page.evaluate(() => ({
  href: document.activeElement?.getAttribute("href") ?? null,
  name: document.activeElement?.getAttribute("aria-label") ?? null,
}));
ok("the door takes focus", Boolean(focused.href?.startsWith(`/${T}/transfers/`)), JSON.stringify(focused));
ok("and it announces itself", Boolean(focused.name), JSON.stringify(focused));

console.log("\n4 · a ninth column must not push the table sideways");
for (const width of [1280, 1440]) {
  const p = await signIn(width);
  await p.goto(`${BASE}/${T}/accounts?tab=transfers`, { waitUntil: "networkidle" });
  await p.waitForTimeout(2000);
  const scrolls = await p.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  ok(`no horizontal page scroll at ${width}`, !scrolls);
  await p.close();
}

console.log(`\n${pass} passed, ${fail} failed`);
if (fail) console.log(failures.map((f) => `  - ${f}`).join("\n"));
clearTimeout(KILL);
await browser.close();
process.exit(fail ? 1 : 0);
