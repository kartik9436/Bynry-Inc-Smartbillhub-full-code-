/**
 * RENDERED-OUTPUT CHECK — **a held control over a screen that already exists**,
 * and a refusal with nothing on it, in a real browser.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: no gate in this repository looks at
 * rendered output, and every fault below was found by a browser and by nothing
 * else. `tsc`, 49 portal test files, 482 cases and every gate were green over
 * all four of them.
 *
 * ⚠ **AND IT IS THE MIRROR OF THE CHECK EVERY WAVE ALREADY MAKES.** A wave
 * tests ITS OWN screen at ITS OWN address; the question *has the door started
 * pointing at it* belongs to nobody, which is `DEF-CWP-3925` and is now three
 * outbreaks old. Steps 1 and 2 assert a DOOR — by ADDRESS and by the SCREEN ID
 * it opens — rather than that a control rendered.
 *
 * WHAT IT ASSERTS
 *   1 · `CWP-046`'s *Something else* card is a LINK to `/…/portal/ask-a-question`
 *       and pressing it lands on `CWP-054`. It was greyed over that screen for
 *       32 hours. The three still-held cards are counted, so releasing one by
 *       accident fails here too.
 *   2 · `CWP-038` at a `$0.00` balance HOLDS *Show me where it goes* and says
 *       *"Enter an amount above zero."* — and raises no page error. It used to
 *       do nothing at all, silently, on a `422` nobody caught.
 *   3 · `CWP-008`'s *Check →* carries its reason, and NO disabled control on
 *       the screen lacks one (`BR-SHL-025`).
 *   4 · `CWP-027`'s *Pay* is a LINK to `/pay-now` and pressing it lands on
 *       `CWP-038`; the bill NUMBER beside it is a link and lands on `CWP-028`;
 *       `CWP-032`'s *Query this reading* is a link to that bill's dispute
 *       address and lands on `CWP-055` (`DEF-CWP-3962`, `DEF-CWP-3954`). All
 *       three were `HeldButton`s or bold text over screens that had shipped —
 *       the third and fourth outbreak of section 1's fault in one week.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   eval "$(10-scripts/proof-db.sh clone fix2 --export)"    # or any seeded demo
 *   DJANGO_SETTINGS_MODULE=config.settings.local python3 06-backend/manage.py migrate
 *   DJANGO_SETTINGS_MODULE=config.settings.local python3 06-backend/manage.py seed_portal_demo
 *   # ⚠ and enrol a login by hand — nothing in the repo does (lane E finding 8)
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8177 --noreload &
 *   (cd 07-frontend && ./node_modules/.bin/vite build && \
 *      STATIC_DIR=$PWD/dist PORT=4377 API_PROXY_TARGET=http://127.0.0.1:8177 node server.mjs &)
 *   BASE=http://127.0.0.1:4377 node 10-scripts/render-checks/fix2-holds-and-refusals.mjs
 *
 * ⚠ **PASS `STATIC_DIR` AND MATCH THE HASH.** A running `server.mjs` serves
 * whatever `dist/` held when it started, forever, and resolves `dist/` from ITS
 * OWN directory — so a worktree run silently serves the shared checkout's
 * bundle (lane E finding 11):
 *   curl -s $BASE/index.html | grep -o 'index-[A-Za-z0-9_-]*\.js'
 *
 * ⚠ **A `429` ON A `public/` ROUTE IS THE GUEST THROTTLE REFUSING THIS SCRIPT
 * AND IS CORRECT** (`NFR-39`). It is printed, not asserted on.
 *
 * PROVEN RED FIRST, TWICE, THROUGH THIS SAME ENTRY POINT (law 7, 2026-09-05).
 * **14 assertions.** With `something_else` re-held on the API and the SAME
 * bundle served, 2 fail — *it no longer says Not online yet* and *it is not a
 * held control any more*. With `PayNow.tsx` and `StartService.tsx` reverted to
 * what shipped and the bundle rebuilt, 5 fail, including
 * *pressing it raises no page error and no 4xx*, which the first draft of this
 * file **could not fail at all** because it read the state without clicking.
 * All 14 green on `sbh_lanee_fresh` afterwards, and the tree was restored and
 * rebuilt after each proof.
 *
 * ⚠ **WRITE ITS OUTPUT UNDER THE SESSION SCRATCHPAD, NOT BARE `/tmp`.** `/tmp`
 * is shared by every lane in this container: a `/tmp/red1.txt` from this
 * lane's first red proof was overwritten by another lane's vitest run within
 * the hour, and the replacement looked like a perfectly good test log.
 *
 * Node 22 + playwright. Reads nothing, writes nothing.
 */
import { existsSync } from "node:fs";
import { createRequire } from "node:module";

// ⚠ **RESOLVED FROM `07-frontend`, EXPLICITLY.** Node resolves a bare import
// from the SCRIPT's own directory upward — never from the working directory —
// so `import … from "playwright"` in a file under `10-scripts/` fails with
// ERR_MODULE_NOT_FOUND however you invoke it, and the repo root has no
// `node_modules`. `cwp_portal_walkthrough.mjs` records paying for this once
// already; a comment telling the reader to run it from `07-frontend` is not a
// guarantee (hard-won law 1). This is.
const require = createRequire(new URL("../../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");
// The walkthrough's own default. `PLAYWRIGHT_BROWSERS_PATH` alone is not enough
// when the installed build number and the one playwright wants differ.
const CHROME = process.env.PW_CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

const BASE = process.env.BASE ?? "http://127.0.0.1:4377";
const TENANT = "pine-hill";
// ⚠ **THE LOGIN DECIDES WHAT THIS PROVES** — the walkthrough's own sentence. A
// customer with no bills exercises section 4 in its EMPTY state and skips every
// assertion in it, which reads as a clean run. `PORTAL_LOGIN` so the landlord
// (bills, a final bill, three accounts) can be driven without editing this file.
const LOGIN = process.env.PORTAL_LOGIN ?? "ana@example.test";
const PASSWORD = "Pine-Hill-2026!";
let bad = 0;
const ok = (good, msg) => { if (!good) bad++; console.log(`${good ? "  ok " : "  ✗  "} ${msg}`); };

const browser = await chromium.launch(existsSync(CHROME) ? { executablePath: CHROME } : {});
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
const jsErrors = [];
const http4xx = [];
page.on("pageerror", (e) => jsErrors.push(String(e).slice(0, 160)));
page.on("response", (r) => { if (r.status() >= 400) http4xx.push(`${r.status()} ${r.url().replace(BASE, "")}`); });

// sign in through the API so the session cookie is real
const res = await page.request.post(`${BASE}/api/${TENANT}/portal/auth/sign-in`, {
  data: { email: LOGIN, password: PASSWORD },
});
console.log(`sign-in ${res.status()}`);

// ── 1 · CWP-046 · the *Something else* card ────────────────────────────────
console.log("\n── CWP-046 · Requests ──");
await page.goto(`${BASE}/${TENANT}/portal/requests`, { waitUntil: "networkidle" });
await page.waitForSelector('[data-screen="CWP-046"]', { timeout: 20000 });
const card = page.locator('[data-errand="something_else"]');
ok((await card.count()) === 1, "the *Something else* card is on the page");
const cardText = (await card.innerText()).replace(/\s+/g, " ");
console.log(`     card reads: ${cardText}`);
ok(!cardText.includes("Not online yet"), "it no longer says *Not online yet — ring us*");
ok((await card.locator('[data-held="true"]').count()) === 0, "it is not a held control any more");
const href = await card.locator("a").first().getAttribute("href");
console.log(`     Start → ${href}`);
ok(href === `/${TENANT}/portal/ask-a-question`, "the door goes to /pine-hill/portal/ask-a-question, by ADDRESS");
const stillHeld = await page.$$eval('[data-errand] [data-held="true"]', (n) => n.length);
ok(stillHeld === 3, `three cards are still held and honest (found ${stillHeld})`);

// press it, and land on the screen it names
await card.locator("a").first().click();
await page.waitForSelector("[data-screen]", { timeout: 20000 });
const landed = await page.locator("[data-screen]").first().getAttribute("data-screen");
const heading = (await page.locator("h1").first().innerText().catch(() => "")).replace(/\s+/g, " ");
console.log(`     landed on ${landed} · ${heading}`);
ok(landed === "CWP-054", "pressing it opens CWP-054, by SCREEN ID");

// ── 2 · CWP-038 · Pay now at a zero balance ───────────────────────────────
console.log("\n── CWP-038 · Pay now ──");
const accounts = await (await page.request.get(`${BASE}/api/${TENANT}/portal/my-accounts`)).json();
const rows = accounts.accounts ?? [];
console.log(`     ${rows.length} accounts: ${rows.map((r) => `${r.balance ?? r.owing}`).join(" · ")}`);
const zero = rows.find((r) => /^0(\.0+)?$/.test(String(r.balance ?? r.owing ?? "")));
const target = zero ?? rows[0];
if (!zero) console.log("     ⚠ no $0.00 account in this fixture — driving the first one");
await page.goto(`${BASE}/${TENANT}/portal/pay-now?account=${target.account_id}`, { waitUntil: "networkidle" });
await page.waitForSelector('[data-screen="CWP-038"]', { timeout: 20000 });
const before = jsErrors.length, before4 = http4xx.length;
const seeLive = await page.$$eval("[data-see]", (n) => n.length);
const seeHeldReason = await page
  .$$eval("[data-see-control] [data-held='true']", (n) =>
    n.map((x) => (x.textContent ?? "").replace(/\s+/g, " ").trim()))
  .catch(() => []);
console.log(`     see control: ${seeLive ? "LIVE" : "HELD"} ${seeHeldReason.join(" | ")}`);
if (zero) {
  ok(seeLive === 0, "at $0.00 the *Show me where it goes* control is HELD, not live");
  ok(seeHeldReason.join(" ").includes("Enter an amount above zero."),
     "and it says *Enter an amount above zero.* rather than nothing at all");
  const pay = await page.locator("[data-pay-control] button").getAttribute("title");
  console.log(`     pay control title: ${pay}`);
  // ⚠ The SERVER's reason outranks the local one and always did (`heldSentence`
  // checks `screen.held_reason` first). This fixture's tenant has no payment
  // provider connected, so *"We cannot take card payments yet."* is the truer
  // fact and is the right thing to say. What must never appear is the empty
  // string or *"See where it goes first."*, which would send a customer back to
  // a button that is itself held.
  ok(typeof pay === "string" && pay.trim() !== "" && pay !== "See where it goes first.",
     `the Pay control holds on a true sentence, not on an empty one or a circular one`);

  // ⚠ **PRESS IT, BECAUSE THE DEFECT ONLY HAPPENS WHEN SOMEBODY PRESSES IT.**
  // The first draft of this file asserted `no new page error` WITHOUT clicking,
  // which is true on the broken screen too: the 422 fires on the press. A check
  // whose output cannot distinguish pass from fail is worse than none, because
  // it is trusted (hard-won law 11's own words, on a different mechanism).
  // Clicking a disabled button is a no-op, so this is safe on the fixed screen
  // and is the whole test on the broken one.
  await page.locator("[data-see-control] button").first().click({ force: true }).catch(() => {});
  await page.waitForTimeout(1200);
  ok(jsErrors.length === before && http4xx.length === before4,
     `pressing it raises no page error and no 4xx (was 422 VAL-003, swallowed)`);
  // And the customer is TOLD something either way — the reason under the held
  // control, or a drawn refusal. "Nothing happened and nothing was said" is the
  // defect, and it is the only outcome this rejects.
  const said = (await page.locator('[data-see-control], [data-see-refused]').allInnerTexts())
    .join(" ").replace(/\s+/g, " ").replace("Show me where it goes", "").trim();
  console.log(`     after pressing, the screen says: ${JSON.stringify(said)}`);
  ok(said !== "", "the customer is told something rather than nothing at all");
} else {
  ok(seeLive === 1, "with a balance to pay the control is LIVE");
}

// ── 3 · CWP-008 and CWP-042 · a disabled control says why ──────────────────
console.log("\n── CWP-008 · Can I get service here ──");
await page.goto(`${BASE}/${TENANT}/portal/start-service`, { waitUntil: "networkidle" });
await page.waitForSelector('[data-screen="CWP-008"]', { timeout: 20000 });
const check = page.locator('[data-action="check"]');
ok(await check.isDisabled(), "*Check →* is disabled before anything is typed");
const checkTitle = await check.getAttribute("title");
console.log(`     Check → title: ${JSON.stringify(checkTitle)}`);
ok(checkTitle === "Type an address first.", "and it now SAYS why");
const noReason = await page.$$eval("button[disabled]:not([data-held] button)", (n) =>
  n.filter((b) => !(b.getAttribute("title") ?? "").trim()).map((b) => (b.textContent ?? "").trim()));
ok(noReason.length === 0, `no disabled control on CWP-008 lacks a reason (${JSON.stringify(noReason)})`);

// ── 4 · the two holds DEF-CWP-3954's lane released ────────────────────────
// ⚠ **BOTH WERE `HeldButton`s OVER SCREENS THAT HAD ALREADY LANDED**, which is
// the same fault as section 1 and the third and fourth outbreak of it in a
// week. They are asserted the same way and for the same reason: **pressed**,
// then read by SCREEN ID. Reading the control's state without pressing is true
// on the broken screen too.
console.log("\n── CWP-027 · Bills · the Pay control (DEF-CWP-3962) ──");
await page.goto(`${BASE}/${TENANT}/portal/bills`, { waitUntil: "networkidle" });
await page.waitForSelector('[data-screen="CWP-027"]', { timeout: 20000 });
// ⚠ **THE SKIP IS KEYED ON WHETHER THERE ARE BILLS, NOT ON WHETHER THERE ARE
// LINKS — AND THE FIRST DRAFT OF THIS BLOCK HAD IT THE OTHER WAY ROUND.** It
// skipped when `[data-bill-link]` was absent, which is precisely the defect
// state: on the red proof four of its six assertions printed *skipped* instead
// of failing. A check whose output cannot distinguish pass from fail is worse
// than none, because it is trusted (`DEF-182`). A login with no bills is the
// only honest skip here.
const billRows = await page.$$eval('[data-testid="bills"] tbody tr', (n) => n.length).catch(() => 0);
console.log(`     ${billRows} bill row(s) on this login`);
if (billRows === 0) {
  console.log("     ⚠ no bills on this login — nothing to open; skipped");
} else {
  const payCell = page.locator("[data-bills-pay]");
  ok((await payCell.count()) === 1, "the Pay control is on the page");
  const payText = (await payCell.innerText().catch(() => "")).replace(/\s+/g, " ");
  console.log(`     pay control reads: ${payText}`);
  ok(!payText.includes("Online payment arrives later this year"),
     "it no longer says *Online payment arrives later this year*");
  ok((await payCell.locator('[data-held="true"]').count()) === 0, "it is not a held control any more");
  const payHref = await payCell.locator("a").first().getAttribute("href").catch(() => null);
  console.log(`     Pay → ${payHref}`);
  ok(payHref === `/${TENANT}/portal/pay-now`, "the door goes to /pine-hill/portal/pay-now, by ADDRESS");
  if (payHref) {
    await payCell.locator("a").first().click();
    await page.waitForSelector("[data-screen]", { timeout: 20000 });
    const paidLanded = await page.locator("[data-screen]").first().getAttribute("data-screen");
    console.log(`     landed on ${paidLanded}`);
    ok(paidLanded === "CWP-038", "pressing it opens CWP-038, by SCREEN ID");
  } else {
    ok(false, "pressing it opens CWP-038, by SCREEN ID — there was no link to press");
  }

  // ⚠ **AND THE BILL NUMBERS BESIDE IT WERE BOLD TEXT** — the same row, the
  // same defect. Five screens hang off this one anchor, so it is pressed too.
  await page.goto(`${BASE}/${TENANT}/portal/bills`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-027"]', { timeout: 20000 });
  const links = await page.$$eval("[data-bill-link]", (n) => n.length);
  ok(links === billRows, `every bill number is a link (${links} of ${billRows})`);
  if (links > 0) {
    const billLink = page.locator("[data-bill-link]").first();
    const number = (await billLink.innerText()).trim();
    const billHref = await billLink.getAttribute("href");
    console.log(`     ${number} → ${billHref}`);
    ok(billHref === `/${TENANT}/portal/bills/${encodeURIComponent(number)}`,
       "the bill NUMBER is the link text and the path segment (B14 rule 31)");
    await billLink.click();
    await page.waitForSelector("[data-screen]", { timeout: 20000 });
    const billLanded = await page.locator("[data-screen]").first().getAttribute("data-screen");
    console.log(`     landed on ${billLanded}`);
    ok(billLanded === "CWP-028", "pressing it opens CWP-028, by SCREEN ID");
  } else {
    ok(false, "the bill NUMBER is the link text and the path segment — no link was drawn");
    ok(false, "pressing it opens CWP-028, by SCREEN ID — there was no link to press");
  }
}

console.log("\n── CWP-032 · the final bill's *Query this reading* (DEF-CWP-3962) ──");
await page.goto(`${BASE}/${TENANT}/portal/final-bill`, { waitUntil: "networkidle" });
await page.waitForSelector('[data-screen="CWP-032"]', { timeout: 20000 });
const query = page.locator('[data-query-reading="open"]');
if ((await query.count()) === 0) {
  console.log("     ⚠ this account has no unsettled final bill — the control is not drawn; skipped");
} else {
  const queryText = (await query.innerText()).replace(/\s+/g, " ");
  console.log(`     query control reads: ${queryText}`);
  const queryHref = await query.locator("a").first().getAttribute("href");
  console.log(`     Query this reading → ${queryHref}`);
  ok(typeof queryHref === "string" && /\/portal\/bills\/.+\/dispute$/.test(queryHref),
     "the door goes to the DISPUTE screen for this bill's number, by ADDRESS");
  ok(!queryText.includes("Ring us to query this"), "it no longer says *Ring us to query this*");
  await query.locator("a").first().click();
  await page.waitForSelector("[data-screen]", { timeout: 20000 });
  const queryLanded = await page.locator("[data-screen]").first().getAttribute("data-screen");
  console.log(`     landed on ${queryLanded}`);
  ok(queryLanded === "CWP-055", "pressing it opens CWP-055, by SCREEN ID");
}

console.log("\n── errors seen anywhere ──");
console.log(`  JS errors: ${jsErrors.length ? jsErrors.join(" | ") : "none"}`);
console.log(`  >=400:     ${http4xx.length ? http4xx.join(" | ") : "none"}`);
await browser.close();
console.log(`\n${bad === 0 ? "ALL CHECKS PASSED" : `${bad} CHECK(S) FAILED`}`);
process.exit(bad === 0 ? 0 : 1);
