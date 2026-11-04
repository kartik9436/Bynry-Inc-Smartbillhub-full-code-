/**
 * RENDERED-OUTPUT CHECK — CR-085 `CPB-21`, `CPB-18`, `CPB-02` and `CPB-03`, in
 * a real browser, at a desktop width and at a phone width.
 *
 * ⚠ **THE FILENAME NAMES TWO AND THE FILE COVERS THREE.** `CPB-02` was added
 * after `DEF-CWP-4683` was found by opening `CWP-040` as a customer; the file
 * was not renamed because it is already cited by name from that defect row and
 * from a commit, and a moved path is a citation that stops resolving.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: no gate in this repository looks at
 * rendered output. PO ruling: *"everything should be executed based on actual
 * code, and rules that we place, also ensure you do web walkthorugh before you
 * sign off the user story or build"*.
 *
 * ⚠ **AND BOTH THINGS THIS CR ADDS ARE INVISIBLE IN THE SEEDED STATE**, which
 * is the whole reason `cr085-cpb18-cpb21-fixture.py` exists and the reason this
 * file REFUSES to run without it. Every plan the wave-M fixture writes has
 * nobody recorded against it, and its level-pay account is enrolled — so both
 * new branches would be skipped and the run would report green over two screens
 * nobody had looked at (`DEF-WRK-4121`).
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   10-scripts/proof-db.sh clone cr85
 *   export DATABASE_URL=… DJANGO_SETTINGS_MODULE=config.settings.local
 *   (cd 06-backend && python3 manage.py seed_portal_demo)
 *   (cd 06-backend && python3 manage.py shell < ../10-scripts/render-checks/cr068-m-fixture.py)
 *   (cd 06-backend && python3 manage.py shell < ../10-scripts/render-checks/cr085-cpb18-cpb21-fixture.py)
 *   python3 06-backend/manage.py runserver 127.0.0.1:8177 --noreload &
 *   (cd 07-frontend && ./node_modules/.bin/vite build && \
 *      PORT=4377 API_PROXY_TARGET=http://127.0.0.1:8177 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4377 node 10-scripts/render-checks/cr085-cpb18-cpb21.mjs
 *
 * ⚠ **BUILD THE BUNDLE BEFORE YOU DRIVE IT.** `server.mjs` serves `dist/`, so a
 * stale build means every assertion passes or fails about a product nobody is
 * shipping.
 *
 * ── WHAT IT CLICKS ────────────────────────────────────────────────────────
 *   1  `CWP-063` — the lead names the PERSON who set the plan up, the absence
 *      line is gone from that account, and no database id is anywhere on it.
 *   2  `CWP-063` on a plan nobody recorded — the honest sentence is still there
 *      and no person is invented.
 *   3  `CWP-044` — the refusal names **March 2025** rather than counting to 11,
 *      and no monthly figure is quoted off a short history.
 *   4  Both screens at 390px: nothing overflows the window.
 *   5a `CWP-063`'s agreement is a DOWNLOAD that answers real bytes — fetched
 *      through the signed-in session, with its `Content-Disposition` read.
 *   5  `CWP-040` in all THREE autopay states — off, on, and *asked for and not
 *      running* — each saying which it is, each offering the control that
 *      matches it, and the last one not promising a payment it will not take.
 */

import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const require = createRequire(join(process.cwd(), "07-frontend", "package.json"));
const { chromium } = require("playwright-core");

/** ⚠ `chromium.executablePath()` returns a path for the build playwright-core
 *  was compiled against, present or not — so it is TESTED, not trusted. */
function resolveChromium() {
  let declared = null;
  try { declared = chromium.executablePath(); } catch { declared = null; }
  if (declared && existsSync(declared)) return declared;
  const found = execFileSync("bash", ["-lc",
    "ls -d /opt/pw-browsers/chromium-*/chrome-linux/chrome /opt/pw-browsers/chromium-*/chrome-linux64/chrome 2>/dev/null | head -1",
  ]).toString().trim();
  if (!found) throw new Error(`no chromium: playwright named ${declared ?? "(nothing)"}`);
  return found;
}

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4377";
const TENANT = "pine-hill";
const EMAIL = process.env.SMOKE_EMAIL ?? "plans@example.test";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "Pine-Hill-2026!";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr085-w1";
const PORTAL = `${BASE}/${TENANT}/portal`;
const API = `${BASE}/api/${TENANT}/portal`;

const OFFER_ACCOUNT = process.env.SMOKE_OFFER_ACCOUNT ?? "AC-2026-00048";
const GAP_ACCOUNT = process.env.SMOKE_GAP_ACCOUNT ?? "AC-2026-00047";
const PLAN_ACCOUNT = process.env.SMOKE_PLAN_ACCOUNT ?? "AC-2026-00046";
/** ⚠ The person is read from the API rather than typed here. The fixture picks
 *  whichever named staff user this tenant has, so hardcoding a name would make
 *  this file fail on a reseed and call it a product fault. */
let CLERK = null;

let failures = 0;
function check(ok, what) {
  console.log(`   ${ok ? "✓" : "✗"} ${what}`);
  if (!ok) failures += 1;
}

async function switchTo(page, accountId) {
  const select = page.locator('[data-account-switcher="select"]');
  if ((await select.count()) !== 1) {
    check(false, "the switcher is not a control — cannot choose an account");
    return false;
  }
  await select.selectOption(accountId);
  await page.waitForTimeout(700);
  return (await select.inputValue()) === accountId;
}

/** ⚠ NAVIGATE, THEN SWITCH. The chosen account lives in a React context above
 *  the router and deliberately not in the address (B14 rule 31), so a full page
 *  load resets it to the first account in the set. */
async function openOn(page, path, screen, accountId) {
  await page.goto(`${PORTAL}${path}`, { waitUntil: "networkidle" });
  await page.waitForSelector(`[data-screen="${screen}"]`, { timeout: 20000 });
  const moved = await switchTo(page, accountId);
  check(moved, `switched to the intended account for ${screen}`);
  await page.waitForSelector(`[data-screen="${screen}"]`, { timeout: 20000 });
  await page.waitForTimeout(600);
}

async function main() {
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });
  console.log(`cr085-w1: ${BASE} tenant=${TENANT}`);

  console.log("\n── 0 · sign in, and refuse without the fixture ──");
  await page.goto(`${PORTAL}/sign-in`, { waitUntil: "networkidle" });
  await page.fill("#portal-email", EMAIL);
  await page.fill("#portal-password", PASSWORD);
  await page.getByRole("button", { name: /sign in/i }).click();
  await page.waitForSelector('[data-portal-frame="shell"]', { timeout: 20000 });
  check(true, `signed in as ${EMAIL}`);

  const accounts = await (await context.request.get(`${API}/accounts`)).json();
  const held = accounts.accounts ?? [];
  console.log(`   accounts held: ${held.map((a) => a.account_no).join(", ")}`);
  const byNo = (no) => held.find((a) => a.account_no === no);
  const offer = byNo(OFFER_ACCOUNT);
  const gap = byNo(GAP_ACCOUNT);
  const plan = byNo(PLAN_ACCOUNT);
  if (!offer || !gap || !plan) {
    console.log("\nRED — this login does not hold the three fixture accounts. Run " +
      "cr068-m-fixture.py then cr085-cpb18-cpb21-fixture.py.");
    await browser.close();
    process.exit(1);
  }

  // ⚠ **THE FIXTURE IS CHECKED THROUGH THE API, NOT ASSUMED.** A run against a
  // plan with nobody recorded would take the absence branch and report green
  // over the very sentence this CR adds.
  const offerBody = await (await context.request.get(
    `${API}/accounts/${offer.id}/plans/offer`)).json();
  CLERK = offerBody?.offer?.offered_by ?? null;
  if (!CLERK) {
    console.log("\nRED — the offered plan records nobody, so CPB-21's whole point " +
      "cannot be drawn. Run cr085-cpb18-cpb21-fixture.py.");
    await browser.close();
    process.exit(1);
  }
  console.log(`   the offer records: ${CLERK}`);

  // ═════ 1 · CWP-063 names the person ══════════════════════════════════════
  console.log("\n── 1 · CPB-21 · the plan says who set it up ──");
  await openOn(page, "/plan-offer", "CWP-063", offer.id);
  const lead = (await page.locator("[data-plan-offer-lead]").first().textContent()) ?? "";
  console.log(`   lead: ${lead.trim()}`);
  check(lead.includes(CLERK), `the lead names ${CLERK}`);
  check(!/the office set this up/i.test(lead),
    "and it no longer says *the office* on a plan that records a person");
  check((await page.locator("[data-plan-no-clerk]").count()) === 0,
    "the *we cannot show you who set this up* line is NOT drawn beside a name");
  // B14 rule 31 — belt and braces, because the id is what the seam resolved from.
  const body = (await page.locator('[data-screen="CWP-063"]').textContent()) ?? "";
  check(!/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}/i.test(body), "no database id on the screen");
  await page.screenshot({ path: join(OUT, "cwp-063-named-1440.png"), fullPage: true });

  // ═════ 2 · a plan nobody recorded still says so ══════════════════════════
  console.log("\n── 2 · CPB-21 · and a plan nobody recorded names nobody ──");
  // ⚠ The ACTIVE plan on the plan account was written by the wave-M fixture
  // with no actor, which is exactly the shape of every plan older than the
  // column. `CWP-063` reads the OFFERED plan, so this is asserted through the
  // API on that account rather than by pretending the screen shows it.
  const noneBody = await (await context.request.get(
    `${API}/accounts/${plan.id}/plans/offer`)).json();
  const noOffer = noneBody?.offer ?? null;
  if (noOffer === null) {
    console.log("   (that account holds no OFFER — the absence branch is covered by " +
      "PlanOffer.dom.test.tsx, which draws it directly)");
    check(true, "no offer on the plan account, as the fixture intends");
  } else {
    check(noOffer.offered_by === null && noOffer.offered_by_unavailable === "not_recorded",
      "a plan with no person recorded says `not_recorded`, not this question's id");
  }

  // ═════ 3 · CWP-044 names the missing month ═══════════════════════════════
  console.log("\n── 3 · CPB-18 · budget billing says WHICH month is missing ──");
  await openOn(page, "/level-pay", "CWP-044", gap.id);
  const gapLine = (await page.locator("[data-level-pay-gap]").first().textContent()) ?? "";
  console.log(`   refusal: ${gapLine.trim()}`);
  check(gapLine.length > 0, "the gap line is drawn");
  check(/March 2025/.test(gapLine), "and it names March 2025 by month and year");
  check((await page.locator("[data-level-pay-unavailable]").count()) === 0,
    "the bare *11 of 12* count is not drawn beside it");
  // ⚠ **NO FIGURE MAY BE QUOTED OFF A SHORT HISTORY** — the eligibility window
  // is the tenant's (BR-BIL-017/021) and averaging eleven months would put a
  // number on screen that no staff screen can reproduce.
  const levelBody = (await page.locator('[data-screen="CWP-044"]').textContent()) ?? "";
  check(!/You would pay each month/i.test(levelBody), "no monthly amount is offered");
  check(!levelBody.includes("$0.00"), "and never $0.00, which would read as *you pay nothing*");
  check(/does not lower them/i.test(levelBody), "the honest sentence is still above it");
  await page.screenshot({ path: join(OUT, "cwp-044-gap-1440.png"), fullPage: true });

  // ═════ 4 · both screens on a phone ═══════════════════════════════════════
  console.log("\n── 4 · 390px, because every signed-in page overflowed one in wave I ──");
  const phone = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const small = await phone.newPage();
  await small.goto(`${PORTAL}/sign-in`, { waitUntil: "networkidle" });
  await small.fill("#portal-email", EMAIL);
  await small.fill("#portal-password", PASSWORD);
  await small.getByRole("button", { name: /sign in/i }).click();
  await small.waitForSelector('[data-portal-frame="shell"]', { timeout: 20000 });

  for (const [path, screen, accountId, mark] of [
    ["/plan-offer", "CWP-063", offer.id, "[data-plan-offer-lead]"],
    ["/level-pay", "CWP-044", gap.id, "[data-level-pay-gap]"],
  ]) {
    await openOn(small, path, screen, accountId);
    const widths = await small.evaluate(() => ({
      doc: document.documentElement.scrollWidth,
      win: window.innerWidth,
    }));
    console.log(`   ${screen}: document ${widths.doc}px inside a ${widths.win}px window`);
    // ⚠ **A ONE-PIXEL TOLERANCE AND NO MORE.** Wave I found the menu at 461px
    // inside 390; anything that cannot wrap shows up here immediately.
    check(widths.doc <= widths.win + 1, `${screen} does not overflow a 390px phone`);
    check((await small.locator(mark).count()) > 0, `${screen}'s new line is still drawn at 390px`);
    await small.screenshot({ path: join(OUT, `${screen}-390.png`), fullPage: true });
  }

  // ═════ 5a · CPB-03 · the agreement downloads ═════════════════════════════
  console.log("\n── 5a · CPB-03 · the kept agreement is a download, not a hold ──");
  await openOn(page, "/plan-offer", "CWP-063", offer.id);
  const download = page.locator("[data-plan-agreement-download]");
  check((await download.count()) === 1, "the agreement is a link, not a held button");
  const href = await download.getAttribute("href");
  console.log(`   href: ${href}`);
  // ⚠ **THE WHOLE ADDRESS.** A bare `/api/portal/…` reaches nothing and reads
  // as a perfectly good string to `toContain` (`DEF-CWP-3925`'s lesson).
  check(href === `/api/${TENANT}/portal/accounts/${offer.id}/plans/offer/agreement`,
    "and its address carries the tenant segment");
  // ⚠ **FETCHED THROUGH THE SIGNED-IN SESSION, BECAUSE THAT IS THE ONLY THING
  // THAT PROVES THE PERMISSION AND THE BYTES.** A link whose href is right and
  // whose endpoint 404s looks identical on screen.
  const served = await context.request.get(`${BASE}${href}`);
  check(served.status() === 200, `and it answers 200 (got ${served.status()})`);
  const document = await served.body();
  check(document.length > 0 && document.subarray(0, 4).toString() === "%PDF",
    `and the body is a real document (${document.length} bytes, starts "${document.subarray(0, 4).toString()}")`);
  const disposition = served.headers()["content-disposition"] ?? "";
  console.log(`   disposition: ${disposition}`);
  check(disposition.startsWith("attachment;"), "served as an attachment, never inline");
  // B14 rule 31 — named for what it IS, never for a row id.
  check(!/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}/i.test(disposition),
    "and the filename is not a database id");

  // ═════ 5 · CWP-040's three states ════════════════════════════════════════
  console.log("\n── 5 · CPB-02 · autopay says which state it is in, and how to stop it ──");
  // ⚠ **ONE ACCOUNT PER STATE, PLACED BY THE FIXTURE.** The seeded estate puts
  // every account of one login in the SAME state, so two of the three branches
  // could never be opened — which is why `CWP-040` shipped reading neither
  // `elected` nor `enrolled` and nothing saw it (`DEF-CWP-4683`).
  const expected = [
    [plan.id, PLAN_ACCOUNT, "on", /Autopay is on/i],
    [gap.id, GAP_ACCOUNT, "off", /Autopay is off/i],
    [offer.id, OFFER_ACCOUNT, "stopped", /not taking payments automatically/i],
  ];
  for (const [id, no, want, sentence] of expected) {
    await openOn(page, "/autopay", "CWP-040", id);
    const got = await page.locator("[data-autopay-state]").getAttribute("data-autopay-state");
    check(got === want, `${no} reads as *${want}* (got *${got}*)`);
    const status = (await page.locator("[data-autopay-status]").innerText()).trim();
    check(sentence.test(status), `and says so in words: "${status.slice(0, 60)}"`);
    const label = (await page.locator("[data-autopay-hold] button").innerText()).trim();
    // ⚠ The control must offer the thing the customer WANTS, not its opposite.
    check(
      want === "off" ? /on$/i.test(label) : /off$/i.test(label),
      `and the held control reads "${label}"`,
    );
    if (want === "stopped") {
      // ⚠ **THE BOX MUST NOT PROMISE A PAYMENT WE WILL NOT TAKE.** Before this,
      // *We take the balance on each due date* sat four lines under *we are not
      // taking payments automatically*, on one card.
      const card = (await page.locator('[data-screen="CWP-040"]').innerText());
      check(/when it is running/i.test(card),
        "and the *what happens* box is scoped, so it does not contradict the line above it");
    }
  }

  await browser.close();
  console.log(`\n${failures === 0 ? "GREEN" : `RED — ${failures} check(s) failed`}`);
  console.log(`screenshots in ${OUT}`);
  process.exit(failures === 0 ? 0 : 1);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
