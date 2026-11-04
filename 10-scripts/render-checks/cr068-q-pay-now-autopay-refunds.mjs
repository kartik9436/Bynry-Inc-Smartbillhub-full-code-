/**
 * RENDERED-OUTPUT CHECK — CR-068 wave Q, "Pay now, autopay, refunds and fees",
 * in a real browser.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: no gate in this repository looks at
 * rendered output, and nine defects in one day were found this way and by
 * nothing else. PO ruling 2026-09-03: *"ensure you do web walkthorugh before
 * you sign off the user story or build"*. Wave Q shipped and was stamped AS
 * BUILT at `2.165.0` with this file named at plan line 805 and **absent from
 * disk** (`DEF-CWP-4128`) — so until this run, `CWP-038`, `CWP-040`, `CWP-045`
 * and `CWP-050` had never been opened in a browser by anything.
 *
 * ⚠ **AND THIS IS THE WAVE WHERE A CUSTOMER'S MONEY ACTUALLY MOVES.** Every
 * figure below is the SERVER's — `pay_now_seam.preview` runs `allocate_payment`,
 * the same code that applies the money — and this script asserts that what the
 * browser DREW equals what the wire CARRIED. No arithmetic is done here; a
 * second sum in a test is a second implementation of the rule.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   10-scripts/proof-db.sh clone cwpq --export          # eval the DATABASE_URL
 *   export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false
 *   (cd 06-backend && python3 manage.py migrate && python3 manage.py seed_portal_demo)
 *   (cd 06-backend && python3 manage.py shell < ../10-scripts/render-checks/cr068-q-fixture.py)
 *
 *   (cd 06-backend && python3 manage.py runserver 127.0.0.1:8144 --noreload &)
 *   (cd 07-frontend && ./node_modules/.bin/vite build && \
 *      PORT=4344 API_PROXY_TARGET=http://127.0.0.1:8144 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4344 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr068-q-pay-now-autopay-refunds.mjs
 *
 * ⚠ **TO CHECK IDEMPOTENCY (step 3b) THE SERVER NEEDS A WEBHOOK SECRET, AND
 * NOTHING IN `config/settings/` SETS ONE.** `payments.webhooks.signing_secret`
 * reads `settings.PAYMENT_WEBHOOK_SECRETS`, which is empty unless a deployment
 * fills it, and an absent secret means REFUSE — hard-won law 3, and right: an
 * endpoint that accepted unsigned deliveries would create payments for anyone.
 * The consequence is that on every server in this repository **the webhook
 * refuses every delivery**, and the dedupe beneath it has never run outside
 * `override_settings` in pytest. To exercise it, start the server with a
 * settings module that sets the mapping and pass the same value here:
 *
 *   SMOKE_WEBHOOK_SECRET=<the same secret> node …/cr068-q-…mjs
 *
 * Without it the step SKIPS and says how many assertions did not run, because
 * a declared blind spot with no number attached is indistinguishable from an
 * empty one (law 7).
 *
 * ⚠ **BUILD THE BUNDLE BEFORE DRIVING IT.** `server.mjs` serves `dist/`. A
 * stale `dist/` means every assertion below passes or fails about a build
 * nobody is shipping — which is a check that cannot fail, wearing a green tick.
 *
 * ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** A mid-run reseed
 * looks exactly like a broken screen.
 *
 * ⚠ **AND THIS RUN CONSUMES ITS OWN FIXTURE — IT PAYS.** Step 1 settles both
 * open bills, so the account it used cannot serve the oldest-first step again
 * and a second run STOPS at step 0 saying the account owes `$0.00`. That is the
 * guard working, not a fault: re-run `cr068-q-fixture.py` (it picks a fresh
 * account and names the login after it), or snapshot the database after the
 * fixture and clone it per run — `create database … template …` is 0.3s, and
 * the seeded estate holds very few accounts with TWO open bills.
 *
 * ⚠ **AND RUN THE FIXTURE, OR THIS PROVES ALMOST NOTHING.** `seed_portal_demo`
 * leaves the tenant with **no saved instruments and no payments provider**, so
 * every Pay control is held, `CWP-045` says *nothing is coming back* and
 * `CWP-050` says *nothing to pay*. That run is GREEN and exercises the one
 * state where the screens have no work to do — `DEF-WRK-4121`'s exact shape.
 * **So step 0 below asserts the state is really there before anything else
 * runs, and stops the walkthrough if it is not.**
 *
 * ── WHAT IT CLICKS (the wave Q demo script, 10-execution-plan.md §Wave Q) ──
 *   0  The state this run needs, asserted on the WIRE before a screen opens:
 *      two OPEN bills, a saved method, a connected provider, `can_pay`.
 *   1  `CWP-038` — the *where it will go* panel is STANDING and names the
 *      oldest bill BEFORE anything is pressed; the consequence bullets name
 *      the method and the bill; **Pay ✓** writes ONE payment, one audit row
 *      naming the portal actor, and `CWP-041` reads *Cleared* the same minute.
 *   2  *Another amount* `$40.00` against two open bills → the panel puts it on
 *      the OLDER bill by the tenant's own rule, and states what that bill will
 *      owe afterwards, **before** anything commits.
 *   3  The sandbox gateway is switched to **time out**: the screen says the
 *      provider did not answer, **no payment row is written**, and the retry
 *      presents the SAME idempotency key the first attempt minted.
 *   3b The inbound webhook, delivered FOUR times: one settlement writes one
 *      payment; the same event id again writes nothing and answers `duplicate`;
 *      **a different event id DOES write a second row** — the control, without
 *      which "no second row" proves nothing; and a forged signature is refused
 *      by name. Needs `SMOKE_WEBHOOK_SECRET`; skips LOUDLY, with the count of
 *      what it did not check, when that is absent.
 *   4  `CWP-040` — *Turn autopay on* is held on `no_automatic_charge`, the
 *      *next few* table draws, and an unbilled month shows TWO em dashes.
 *   5  `CWP-045` — the refund timeline; money that came in on a card goes back
 *      **by cheque** and the screen says why; a voided refund stays listed.
 *   6  `CWP-050` — `$185.00` + `$150.00` = **`$335.00`** to pay now, `$25.00`
 *      waived, struck through and in NEITHER total; the Pay control is held on
 *      `no_fee_payment_path` and there is no amount box beside it.
 *   7  Every screen: no database id, no rule id, no internal code (B14 rules
 *      31 and 32), and every hold that is drawn has a row in the register
 *      `g103_holds_cannot_rot.py` reads.
 *
 * ⚠ **WHAT WOULD MAKE EACH CHECK PASS WRONGLY** is asked of every assertion
 * here, because a check you cannot describe a false pass for is a check you do
 * not understand (hard-won law 7). The three that needed real care:
 *   * a total that matches because BOTH sides are zero — so step 0 refuses a
 *     zero balance and every money assertion is against a figure > 0;
 *   * `[].every(...)` is `true` — so every list assertion states its COUNT
 *     first and fails an empty list by name;
 *   * "no payment row was written" is unfalsifiable if the count was never
 *     read before — so step 3 reads the count BEFORE the attempt and again
 *     after, and prints both.
 */

import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

import { createHmac } from "node:crypto";

import { Gaps } from "./lib/knownGaps.mjs";
import { attachTimings } from "./lib/timings.mjs";

const require = createRequire(join(process.cwd(), "07-frontend", "package.json"));
const { chromium } = require("playwright-core");

/**
 * The browser to drive.
 *
 * ⚠ **THE FALLBACK IS GUARDED ON THE FILE EXISTING, NOT ON A THROW** — and
 * that difference is why this run started. `cr068-e-getting-in.mjs` wraps
 * `chromium.executablePath()` in a `try/catch` and falls back on the `catch`;
 * `executablePath()` does not throw when the installed browser is a different
 * revision from the one `playwright-core` was built against. It returns a
 * perfectly well-formed path to a file that is not there
 * (`…/chromium-1234/chrome-linux64/chrome` against an installed `chromium-1194`),
 * so the fallback never fires and the launch dies instead. **A fallback that
 * cannot run is a check that cannot fail wearing the other face** (hard-won
 * law 7), so this one asks the filesystem.
 */
function resolveChromium() {
  let declared = null;
  try {
    declared = chromium.executablePath();
  } catch {
    declared = null;
  }
  if (declared && existsSync(declared)) return declared;
  const found = execFileSync("bash", [
    "-lc",
    "ls -d /opt/pw-browsers/chromium-*/chrome-linux/chrome /opt/pw-browsers/chromium-*/chrome-linux64/chrome 2>/dev/null | head -1",
  ])
    .toString()
    .trim();
  if (!found) {
    throw new Error(
      `no chromium on this machine: playwright names ${declared}, which does not exist, ` +
        "and nothing matches /opt/pw-browsers/chromium-*/chrome-linux*/chrome",
    );
  }
  if (declared) console.log(`   (playwright named ${declared}; using ${found})`);
  return found;
}

/**
 * Which account this run is about — **read from the fixture, never guessed.**
 *
 * ⚠ **THE ACCOUNT MOVES BETWEEN RUNS AND THAT IS DELIBERATE.** This walkthrough
 * PAYS: it settles both open bills, so the account it used last time cannot
 * serve the oldest-first step again. The fixture therefore picks a fresh
 * account each run, names the login after it, and writes both here. A hard-coded
 * email would make every run after the first fail on *"0 open bills"* — a
 * truthful complaint about the fixture, dressed as a fault in the product.
 */
const HANDOFF = process.env.SMOKE_HANDOFF ?? "/tmp/cr068-q/fixture.json";
const handoff = existsSync(HANDOFF) ? JSON.parse(readFileSync(HANDOFF, "utf8")) : {};

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4344";
const TENANT = process.env.SMOKE_TENANT ?? handoff.tenant ?? "pine-hill";
const EMAIL = process.env.SMOKE_EMAIL ?? handoff.email;
const PASSWORD = process.env.SMOKE_PASSWORD ?? handoff.password ?? "Pine-Hill-2026!";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr068-q";
const VIEWPORT = { width: 1440, height: 1000 };

const PORTAL = `${BASE}/${TENANT}/portal`;
const API = `${BASE}/api/${TENANT}/portal`;

/** `US-CWP-050` §4's signed arithmetic — `$185.00 + $150.00`, and `$25.00` in
 *  neither total. Pinned by `cr068-q-fixture.py`, so these are literals. */
const FEES_TO_PAY_NOW = "$335.00";
const FEE_WAIVED = "$25.00";
/** `US-CWP-049` §4's worked refund. */
const REFUND_CHEQUE = "10241";
const REFUND_CARD_LAST_FOUR = "8812";
/** Step 2's part payment. Small enough to leave the older bill still owing,
 *  which is the whole point of the *left owing* column. */
const PART_AMOUNT = "40.00";

mkdirSync(OUT, { recursive: true });

//: ⚠ **A CHECK THAT IS RED BY DESIGN IS A CHECK NOBODY READS.** Two of this
//: wave's signed cases cannot be reached on any running tenant, and both are
//: recorded rather than asserted-and-ignored: the run prints them with their
//: defect ids on every pass, and goes RED the day either one CLOSES and this
//: file still says it has not.
const gaps = new Gaps();

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

/** A hard stop: the run cannot prove what it exists to prove. */
function must(ok, message) {
  check(ok, message);
  if (!ok) {
    console.log(`\nSTOPPING — ${message}`);
    console.log("This walkthrough would otherwise report green over a state that proves nothing.");
    console.log("Run 10-scripts/render-checks/cr068-q-fixture.py and try again.");
    process.exit(1);
  }
}

/** B14 rule 31 and rule 32 — never an id, never an internal code, on screen. */
const FORBIDDEN = [
  /\bBR-[A-Z]{3}-\d{3,5}\b/,
  /\bOQ-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /\bDEF-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
];

async function noInternals(page, where) {
  const text = await page.locator("body").innerText();
  for (const pattern of FORBIDDEN) {
    check(!pattern.test(text), `${where}: nothing matching ${pattern} on screen (B14 rule 31)`);
  }
}

/** Money as the product writes it — `$1,234.56`. Used only to RECOGNISE a
 *  figure on screen, never to compute one. */
const MONEY = /^\$[\d,]+\.\d{2}$/;

const money = (text) => (text ?? "").trim();

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const timings = attachTimings(context);
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });
  console.log(`cr068-q: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);

  // ═════ 0 · THE STATE THIS RUN NEEDS, ON THE WIRE, BEFORE A SCREEN OPENS ══
  //: ⚠ Asserted through the API rather than by reading the screen, for the
  //: reason `cr068-e` gives about `find-account`: a screen that failed to DRAW
  //: a bill and a database that HOLDS no bill look identical in a browser, and
  //: they are opposite faults.
  console.log("\n── 0 · the state the demo script assumes, proved before it is used ──");
  must(
    typeof EMAIL === "string" && EMAIL.length > 0,
    `a login to walk as (from ${HANDOFF}, or SMOKE_EMAIL) — run cr068-q-fixture.py first`,
  );
  const signIn = await context.request.post(`${API}/auth/sign-in`, {
    data: { email: EMAIL, password: PASSWORD },
  });
  must(signIn.ok(), `signed in as ${EMAIL}`);

  const accounts = await (await context.request.get(`${API}/accounts`)).json();
  must(
    Array.isArray(accounts.accounts) && accounts.accounts.length > 0,
    `the login holds ${accounts.accounts?.length ?? 0} account(s)`,
  );
  const account = accounts.accounts[0];
  const accountId = account.id;
  console.log(`      account ${account.account_no}, permissions ${JSON.stringify(account.permissions)}`);

  const position = await (await context.request.get(`${API}/accounts/${accountId}/pay-now`)).json();
  const openBills = (position.bills ?? []).filter((one) => Number(one.open_balance) > 0);
  //: ⚠ **THE `DEF-WRK-4121` GUARD.** Every one of these is a state the screen
  //: needs to have any work to do, and each was ABSENT on a plain
  //: `seed_portal_demo` database.
  must(Number(position.balance) > 0, `the account owes $${Number(position.balance).toFixed(2)} — not zero`);
  must(openBills.length >= 2, `it has ${openBills.length} OPEN bills (the oldest-first step needs two)`);
  must((position.instruments ?? []).length > 0, `${position.instruments.length} saved method(s)`);
  must(position.can_pay === true, `can_pay is true (held_reason ${JSON.stringify(position.held_reason)})`);
  check(position.order === "oldest_first", `the tenant's allocation rule is ${position.order}`);
  const oldest = openBills.reduce((a, b) => (a.issued_on <= b.issued_on ? a : b));
  console.log(`      oldest open bill ${oldest.number} (issued ${oldest.issued_on}) owes $${Number(oldest.open_balance).toFixed(2)}`);

  //: The payment count BEFORE anything is pressed. Step 3's *nothing was
  //: written* is unfalsifiable without it.
  //: ⚠ **THE LIST BODY'S KEY IS `money`, NOT `payments`.** Written as
  //: `body.payments ?? []` the first time, which is `[]` for a body that does
  //: not carry that key — so the count read 0 before AND after a payment that
  //: really was written, and `0 === 0 + 1` happened to fail. Written as `>=` it
  //: would have PASSED over a screen that recorded nothing (hard-won law 7:
  //: ask what would make this check pass wrongly). Hence the guard below.
  const paymentsBefore = await (await context.request.get(`${API}/payments`)).json();
  must(
    Array.isArray(paymentsBefore.money),
    `the money list answers a \`money\` array (keys: ${Object.keys(paymentsBefore).join(", ")})`,
  );
  const countBefore = paymentsBefore.money.length;
  console.log(`      ${countBefore} payment row(s) on the account before this run`);

  // ═════ 1 · CWP-038 — the panel STANDS, and the money moves ═══════════════
  console.log("\n── 1 · where it will go, before anything is pressed ──");
  await page.goto(`${PORTAL}/sign-in`, { waitUntil: "networkidle" });
  await page.fill("#portal-email", EMAIL);
  await page.fill("#portal-password", PASSWORD);
  await page.getByRole("button", { name: /sign in/i }).click();
  await page.waitForSelector('[data-portal-frame="shell"]', { timeout: 20000 });

  await page.goto(`${PORTAL}/pay-now`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-038"]', { timeout: 20000 });
  //: ⚠ **STANDING, NOT BEHIND A BUTTON** (delta row 38.1, `DEF-CWP-3970`).
  //: *Show me where it goes* was deleted and the preview is a debounced effect,
  //: so the panel is on screen the moment the page opens. Nothing is clicked
  //: between the load and this assertion, which is what makes it the check.
  await page.waitForSelector("[data-bill='0']", { timeout: 20000 });
  const landedBill = (await page.locator("[data-bill='0']").innerText()).trim();
  check(
    landedBill === oldest.number,
    `the panel names ${landedBill} before anything is pressed (oldest open bill is ${oldest.number})`,
  );
  check(
    (await page.locator("[data-see-refused]").count()) === 0,
    "…and no *see where it goes* control is left on the screen (delta 38.1)",
  );
  const wholePaying = money(await page.locator("[data-paying='0']").innerText());
  check(MONEY.test(wholePaying), `it states what lands on that bill: ${wholePaying}`);
  const orderNote = await page.locator("[data-order]").innerText();
  check(orderNote.trim().length > 0, `the footer states the tenant's rule: "${orderNote.trim()}"`);

  // ═════ 2 · a part payment, and the OLDER bill, before anything commits ═══
  //: ⚠ **THIS RUNS BEFORE THE WHOLE-BALANCE COMMIT AND THAT ORDER IS THE
  //: POINT.** The demo script lists it second, and on the first run it was
  //: written second — by which time step 1 had settled BOTH bills and the
  //: oldest-first case had nothing left to be oldest of. *"only 0 open bill(s)
  //: left"* is a truthful failure and a useless one: the state a check needs
  //: has to exist WHEN the check runs, not when the script was written.
  console.log("\n── 2 · $40.00 against two open bills — oldest first, stated first ──");
  await page.getByRole("radio", { name: /another amount/i }).check();
  await page.fill("#pay-amount", PART_AMOUNT);
  await page.waitForTimeout(900); // the 250 ms debounce, plus the round trip
  const partBill = (await page.locator("[data-bill='0']").innerText()).trim();
  check(
    partBill === oldest.number,
    `$${PART_AMOUNT} lands on ${partBill}, the OLDER bill (${oldest.number}, issued ${oldest.issued_on})`,
  );
  const partRows = await page.locator("[data-bill]").count();
  check(partRows === 1, `and on that bill only — ${partRows} row in the panel, so it is not spread`);
  const owingAfter = money(await page.locator("[data-after='0']").innerText());
  //: ⚠ **THE FIGURE IS THE SERVER'S AND SO IS THE EXPECTATION.** The browser
  //: does no subtraction; what is checked is that the number the screen DREW is
  //: the number `allocate_payment` RETURNED for that bill. A test that
  //: subtracted `$40.00` here would be a second implementation of the rule.
  const preview = await (
    await context.request.post(`${API}/accounts/${accountId}/pay-now/preview`, {
      data: { amount: PART_AMOUNT },
    })
  ).json();
  const wireAfter = (preview.lands_on ?? []).find((one) => one.number === partBill);
  check(
    wireAfter !== undefined && owingAfter === `$${Number(wireAfter.owing_after).toFixed(2)}`,
    `the screen says that bill will owe ${owingAfter} afterwards — the same figure the allocator returned`,
  );
  check(
    MONEY.test(owingAfter) && Number(owingAfter.replace(/[$,]/g, "")) > 0,
    `…and it is a real remaining balance, not a zero that would match anything: ${owingAfter}`,
  );
  await page.screenshot({ path: join(OUT, "2-part-payment.png"), fullPage: true });

  //: The consequence box, and the bullet that names the METHOD (`DEF-CWP-3971`
  //: — it once read *"Takes $155.45 from **.**"*, a sentence naming no method
  //: and ending in a bare full stop).
  console.log("\n── 1b · the consequence, and the commit ──");
  await page.getByRole("radio", { name: /whole balance|everything you owe/i }).check();
  await page.waitForTimeout(900);
  await page.locator("[data-methods] input[type=radio]").first().check();
  await page.waitForTimeout(600); // the 250 ms debounce, plus the round trip
  const consequence = await page.locator('[data-testid="pay-now-consequences"], [data-testid="consequences"]').count();
  const boxText = consequence > 0
    ? await page.locator('[data-testid="pay-now-consequences"], [data-testid="consequences"]').first().innerText()
    : await page.locator('[data-screen="CWP-038"]').innerText();
  check(!/\bfrom\s*\.\s*$/m.test(boxText), "no bullet names an empty method (DEF-CWP-3971)");
  const chosenLabel = (await page.locator("[data-methods] label").first().innerText()).trim();
  console.log(`      paying with: ${chosenLabel.replace(/\s+/g, " ")}`);
  await page.screenshot({ path: join(OUT, "1-pay-now.png"), fullPage: true });

  //: ⚠ **THE COMMIT.** `data-pay-control` is the wrapper the screen puts round
  //: `CommitButton` on purpose: finding it by LABEL would assert a translation
  //: and finding it by variant would break the day another primary lands.
  const payControl = page.locator("[data-pay-control] button");
  check((await payControl.count()) === 1, "one Pay control, in the button row at the foot of the card");
  check(await payControl.isEnabled(), "…and it is pressable, because a method and an amount are chosen");
  await payControl.click();
  await page.waitForSelector("[data-outcome-said]", { timeout: 30000 });
  const outcomeSaid = (await page.locator("[data-outcome-said]").innerText()).trim();
  const paymentNo = (await page.locator("[data-payment-no]").count())
    ? (await page.locator("[data-payment-no]").innerText()).trim()
    : null;
  check(paymentNo !== null, `the confirmation names the payment: ${paymentNo} — "${outcomeSaid}"`);
  //: ⚠ **THE SERIES IS THE TENANT'S AND MAY NOT BE ASSERTED AS A LITERAL.**
  //: The first draft here checked `/^PMT-/`, because `PayNow.tsx`, `models.py`,
  //: `gateway.py`, `cheques.py` and `idempotency.py` all call this *"the PMT-
  //: number"*. It is not: `core/numbering.py` line 332 makes the payment format
  //: tenant-editable and seeds `PY-{YY}{MM}{DD}-{0000}` as the DEFAULT, with
  //: `PMT-{YY}-{00000}` merely one of five options a utility may pick. Pine
  //: Hill emits `PY-260906-0084`. So what is asserted is B14 rule 31's actual
  //: requirement — a human reference and not a row id — and the literal
  //: prefix is left to the tenant, exactly as `data-order` leaves the
  //: allocation rule to the tenant. The stale comments are `DEF-CWP-4131`.
  const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  check(
    paymentNo !== null && !UUID.test(paymentNo) && /^[A-Z]+-[\d-]+$/.test(paymentNo),
    `…and it is a human reference from the tenant's own series, never a row id (B14 rule 31): ${paymentNo}`,
  );
  await page.screenshot({ path: join(OUT, "1-paid.png"), fullPage: true });

  //: ONE row, not two — the immutability and idempotency claim, counted.
  const paymentsAfter = await (await context.request.get(`${API}/payments`)).json();
  const countAfter = (paymentsAfter.money ?? []).length;
  check(
    countAfter === countBefore + 1,
    `exactly ONE payment row was written (${countBefore} → ${countAfter})`,
  );

  //: `CWP-041` reads *Cleared* the same minute (demo script step 1's last clause).
  await page.goto(`${PORTAL}/payments`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-041"]', { timeout: 20000 });
  const moneyList = await page.locator('[data-screen="CWP-041"]').innerText();
  check(
    (await page.locator("[data-money-empty]").count()) === 0,
    "the money list is not empty (an empty list would pass every assertion below)",
  );
  check(/cleared/i.test(moneyList), "…and it carries a CLEARED payment");
  await noInternals(page, "CWP-041");
  await page.screenshot({ path: join(OUT, "1-money-list.png"), fullPage: true });


  // ═════ 3 · the gateway times out, and NOTHING is written ═════════════════
  console.log("\n── 3 · the provider does not answer — no row, and the same key on retry ──");
  const flipped = setSandboxBehaviour("timeout");
  if (!flipped) {
    check(false, "could not switch the sandbox provider to `timeout` — step 3 did not run");
  } else {
    const beforeTimeout = ((await (await context.request.get(`${API}/payments`)).json()).money ?? []).length;
    //: The key is minted by the PREVIEW, before the first request leaves
    //: (`US-CWP-045` TC-7). Read it here so the retry can be compared to it.
    const first = await (
      await context.request.post(`${API}/accounts/${accountId}/pay-now/preview`, {
        data: { amount: "10.00" },
      })
    ).json();
    const firstKey = first.idempotency_key;
    check(typeof firstKey === "string" && firstKey.length > 0, `the preview minted a key: ${firstKey}`);
    const again = await (
      await context.request.post(`${API}/accounts/${accountId}/pay-now/preview`, {
        data: { amount: "10.00", idempotency_key: firstKey },
      })
    ).json();
    check(
      again.idempotency_key === firstKey,
      `a re-price presents the SAME key, never a fresh one (${again.idempotency_key})`,
    );

    await page.goto(`${PORTAL}/pay-now`, { waitUntil: "networkidle" });
    await page.waitForSelector('[data-screen="CWP-038"]', { timeout: 20000 });
    await page.locator("[data-methods] input[type=radio]").first().check();
    await page.getByRole("radio", { name: /another amount/i }).check();
    await page.fill("#pay-amount", "10.00");
    await page.waitForTimeout(900);
    await page.locator("[data-pay-control] button").click();
    await page.waitForSelector("[data-outcome-said]", { timeout: 40000 });
    const said = (await page.locator("[data-outcome-said]").innerText()).trim();
    check(said.length > 0, `the screen says what happened: "${said}"`);
    check(
      (await page.locator("[data-payment-no]").count()) === 0,
      "…and it names NO payment reference, because nothing was recorded",
    );
    check(
      (await page.locator("[data-try-again]").count()) === 1,
      "…and it offers *try again*, which re-sends the key rather than minting one",
    );
    const afterTimeout = ((await (await context.request.get(`${API}/payments`)).json()).money ?? []).length;
    check(
      afterTimeout === beforeTimeout,
      `NO payment row was written (${beforeTimeout} before, ${afterTimeout} after) — a zero is a claim nobody can make`,
    );
    await page.screenshot({ path: join(OUT, "3-timeout.png"), fullPage: true });
    setSandboxBehaviour("approve");
  }

  // ═════ 3b · CAN AN INBOUND WEBHOOK BE MADE TO APPLY TWICE? ══════════════
  //: Hard rule 6. **FOUR deliveries, and the third is the one that makes the
  //: answer mean anything.** *"The second delivery wrote no row"* is worth
  //: nothing on its own — an endpoint that is inert, throttled, misconfigured or
  //: refusing everything for an unrelated reason produces exactly that
  //: observation, and a walkthrough that stopped there would be reporting a shut
  //: door as a working guard. So delivery 3 re-sends the same money under a NEW
  //: event id and REQUIRES a second payment row: only then is delivery 2's
  //: silence the dedupe rather than the door.
  //:
  //: ⚠ **AND IT IS SKIPPED LOUDLY, WITH A NUMBER, WHEN THE SECRET IS ABSENT.**
  //: `signing_secret` reads `settings.PAYMENT_WEBHOOK_SECRETS`, **which nothing
  //: in `config/settings/` sets** — so on a stock server every delivery is
  //: refused `no_secret` (hard-won law 3, and correct). A run without it must
  //: not print four green ticks about a door that is shut; it prints what it
  //: could not check, because a declared blind spot with no number attached is
  //: indistinguishable from an empty one.
  console.log("\n── 3b · the same settlement twice, and the control that proves it ──");
  const WEBHOOK_SECRET = process.env.SMOKE_WEBHOOK_SECRET ?? "";
  if (WEBHOOK_SECRET === "") {
    console.log("   ⏭  SKIPPED — no SMOKE_WEBHOOK_SECRET, so the endpoint refuses every");
    console.log("      delivery `no_secret` and 4 assertions about idempotency did NOT run.");
    console.log("      Start the server with PAYMENT_WEBHOOK_SECRETS set to check them.");
  } else {
    const hook = `${BASE}/api/${TENANT}/portal/webhooks/payments/payments_sandbox`;
    const settlement = (eventId) => ({
      id: eventId,
      type: "payment_intent.succeeded",
      account_id: accountId,
      amount: "25.00",
      currency: "USD",
      posted_at: "2026-09-06T09:00:00Z",
      cleared_at: "2026-09-06T09:00:00Z",
      reference: eventId,
    });
    //: ⚠ **SIGNED OVER THE BYTES THAT ARE SENT, never over a re-serialised
    //: object.** Two JSON encoders disagree about spacing and key order, so a
    //: signature computed over anything but the exact payload fails for a
    //: reason nobody can debug — and that debugging usually ends with somebody
    //: switching verification off.
    const deliver = async (body, badSignature = false) => {
      const raw = JSON.stringify(body);
      const mac = createHmac("sha256", WEBHOOK_SECRET).update(raw).digest("hex");
      const answer = await context.request.post(hook, {
        data: raw,
        headers: {
          "Content-Type": "application/json",
          "X-Signature": `sha256=${badSignature ? "0".repeat(64) : mac}`,
        },
      });
      return answer.json();
    };
    const rows = async () =>
      ((await (await context.request.get(`${API}/payments`)).json()).money ?? []).length;

    const w0 = await rows();
    const d1 = await deliver(settlement("STL-CR068Q-0001"));
    const w1 = await rows();
    check(w1 === w0 + 1, `one signed settlement wrote ONE payment row (${w0} → ${w1})`);

    const d2 = await deliver(settlement("STL-CR068Q-0001"));
    const w2 = await rows();
    check(w2 === w1, `the SAME event id again wrote NOTHING (${w1} → ${w2}) — hard rule 6`);
    check(
      String(d2.status ?? "").toLowerCase() === "duplicate",
      `…and it was RECOGNISED as a replay rather than refused for another reason: status=${JSON.stringify(d2.status)}`,
    );

    //: THE CONTROL.
    const d3 = await deliver(settlement("STL-CR068Q-0002"));
    const w3 = await rows();
    check(
      w3 === w2 + 1 && String(d3.status ?? "") === "accepted",
      `a DIFFERENT event id DID write a second row (${w2} → ${w3}) — so the silence above is the dedupe, not a shut door`,
    );

    const d4 = await deliver(settlement("STL-CR068Q-0003"), true);
    const w4 = await rows();
    check(
      w4 === w3 && d4.signature_verified === false,
      `a BROKEN signature wrote nothing (${w3} → ${w4}) and was refused by name`,
    );
    console.log(`      first=${d1.status} replay=${d2.status} control=${d3.status} forged=${d4.status}`);
  }

  // ═════ 4 · CWP-040 — the switch, and a table that is real ════════════════
  console.log("\n── 4 · autopay: an intent that exists, waiting for a charge that does not ──");
  await page.goto(`${PORTAL}/autopay`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-040"]', { timeout: 20000 });
  const autopay = await (await context.request.get(`${API}/accounts/${accountId}/autopay`)).json();
  const holdWrapper = page.locator("[data-autopay-hold]");
  check((await holdWrapper.count()) === 1, "the switch is DRAWN, not hidden (BR-CWP-056)");
  const holdReason = await holdWrapper.getAttribute("data-autopay-hold");
  check(
    holdReason === autopay.held_reason,
    `it is held on \`${holdReason}\` — the reason the SERVER chose, not one the screen picked`,
  );
  const holdButton = holdWrapper.locator("button");
  check(
    (await holdButton.count()) === 1 && !(await holdButton.first().isEnabled()),
    "…and the button is present and disabled — never hidden, never live-but-inert",
  );
  const reasonText = (await holdWrapper.innerText()).trim();
  const reasonWords = reasonText.split(/\s+/).filter((w) => !/^(Turn|autopay|on)$/i.test(w));
  console.log(`      the refusal reads: "${reasonText.replace(/\s+/g, " ")}"`);
  //: ⚠ **THE CONTROL'S PAINTED WIDTH, NOT ITS CLASS LIST** (`DEF-CWP-4133`).
  //: `Card` is `flex flex-col`, so a control placed directly in it stretches to
  //: the card — 668px of bordered button reading *Your payment methods*, which
  //: is not one of the kit's two button sizes. **The class list is identical
  //: either way**, which is why no test, no `tsc` and no gate could see it and
  //: why the assertion has to ask the browser what it painted. The threshold is
  //: expressed as a FRACTION of the card rather than a pixel count, so it does
  //: not go false the day the layout gets wider.
  //: `ErrandLink` renders a `ButtonLink`, which is an anchor — so the control
  //: is found by its DESTINATION, which is also what `DEF-CWP-3925` asks a test
  //: to assert about a door.
  const methodsDoor = page.locator('a[href$="/payment-methods"]').first();
  if ((await methodsDoor.count()) > 0) {
    const geometry = await methodsDoor.evaluate((el) => {
      const card = el.closest("[data-testid]") ?? el.parentElement;
      return { control: el.getBoundingClientRect().width, card: card.getBoundingClientRect().width };
    });
    check(
      geometry.control < geometry.card * 0.5,
      `*Your payment methods* is ${Math.round(geometry.control)}px inside a ${Math.round(geometry.card)}px card — a control, not a full-width bar (DEF-CWP-4133)`,
    );
  }

  //: `when` is read-only and there is no control to change it (TC-5).
  check(
    (await page.locator("#autopay-when input, #autopay-when select").count()) === 0,
    "*When* is a sentence, not a disabled date picker (US-CWP-047 TC-5)",
  );
  //: ⚠ **TWO EM DASHES ON AN UNBILLED MONTH, NOT ONE** — the AMOUNT is absent
  //: because the story says *not an estimate*, and the DATE is absent because
  //: nothing in this product answers a next due date before the bill is made.
  const slots = await page.locator("[data-slot-amount]").count();
  check(slots > 0, `the *next few* table drew ${slots} row(s) — an empty table would prove nothing`);
  const unbilled = (autopay.next_few ?? []).findIndex((one) => one.state === "not_billed_yet");
  if (unbilled >= 0) {
    const dateCell = money(await page.locator(`[data-slot-date='${unbilled}']`).innerText());
    const amountCell = money(await page.locator(`[data-slot-amount='${unbilled}']`).innerText());
    check(
      dateCell === "—" && amountCell === "—",
      `an unbilled month shows TWO em dashes and no guess: date "${dateCell}", amount "${amountCell}"`,
    );
  } else {
    console.log("      (no NOT BILLED YET row on this account — the two-dash case did not run)");
  }
  //: ⚠ **THE DRAWING'S FIRST ROW HAS NEVER BEEN ON ANY SCREEN.**
  gaps.known(
    (autopay.next_few ?? []).some((one) => one.state === "scheduled"),
    "the NEXT FEW table carries a SCHEDULED row with the amount the customer was told",
    {
      defect: "DEF-PAY-4177",
      why: "nothing writes an AutopayCaptureIntent — BR-PAY-015 records it at bill issue and apps/billing/issue.py does not call record_intent_at_issue, which the server names in its own reply as intent_recording_has_no_caller. US-CWP-047 TC-4 is therefore unprovable in a browser",
    },
  );
  await noInternals(page, "CWP-040");
  await page.screenshot({ path: join(OUT, "4-autopay.png"), fullPage: true });

  // ═════ 5 · CWP-045 — back by cheque, and it says why ═════════════════════
  console.log("\n── 5 · a card refund that goes back by cheque, and says so ──");
  await page.goto(`${PORTAL}/money-back`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-045"]', { timeout: 20000 });
  const moneyBack = await (await context.request.get(`${API}/accounts/${accountId}/money-back`)).json();
  check(
    (await page.locator("[data-money-back-empty]").count()) === 0,
    `the screen has refunds to draw (${(moneyBack.refunds ?? []).length} on the wire)`,
  );
  const refundAmounts = await page.locator("[data-refund-amount]").allInnerTexts();
  check(
    refundAmounts.length === (moneyBack.refunds ?? []).length && refundAmounts.length > 0,
    `${refundAmounts.length} refund panel(s) drawn, one per refund on the wire`,
  );
  for (const drawn of refundAmounts) {
    check(MONEY.test(drawn.trim()), `a refund figure is money to two places: ${drawn.trim()}`);
  }
  const destination = await page.locator("[data-destination]").first().innerText();
  const fallback = await page.locator("[data-fallback-reason]").count();
  check(
    /8812/.test(destination) || new RegExp(REFUND_CARD_LAST_FOUR).test(await page.locator('[data-screen="CWP-045"]').innerText()),
    `the screen names the card the money came in on (…${REFUND_CARD_LAST_FOUR})`,
  );
  const wholeRefundText = await page.locator('[data-screen="CWP-045"]').innerText();
  check(
    wholeRefundText.includes(REFUND_CHEQUE),
    `…and the cheque it was sent as instead (#${REFUND_CHEQUE})`,
  );
  check(
    fallback > 0,
    "…and it states WHY it is not going back the way it came (US-CWP-049 TC-3)",
  );
  //: ⚠ **A VOIDED REFUND IS LISTED AS VOIDED, NOT REMOVED** (`US-CWP-056` TC-4).
  const voided = (moneyBack.refunds ?? []).filter((one) => one.voided_at !== null);
  if (voided.length > 0) {
    check(
      (await page.locator('[data-testid="chip-refund-void"], [data-chip="refund-void"]').count()) > 0
        || /void/i.test(wholeRefundText),
      `the voided refund is still on screen, marked voided (${voided.length} of ${moneyBack.refunds.length})`,
    );
  } else {
    check(false, "no voided refund in the fixture — TC-4 could not be proved");
  }
  check(
    (await page.locator("[data-separating-sentence]").count()) === 1,
    "…and the one line that separates a CREDIT from a REFUND is on the screen",
  );
  await noInternals(page, "CWP-045");
  await page.screenshot({ path: join(OUT, "5-money-back.png"), fullPage: true });

  // ═════ 6 · CWP-050 — $185 + $150 = $335, and $25 in neither total ════════
  console.log("\n── 6 · what starting service will cost ──");
  await page.goto(`${PORTAL}/fees`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-050"]', { timeout: 20000 });
  const fees = await (await context.request.get(`${API}/fees`)).json();
  check(
    (await page.locator("[data-fees-empty]").count()) === 0,
    `the screen has a quote to draw (${(fees.lines ?? []).length} line(s) on the wire)`,
  );
  const feeAmounts = await page.locator("[data-fee-amount]").allInnerTexts();
  check(
    feeAmounts.length === (fees.lines ?? []).length && feeAmounts.length > 0,
    `${feeAmounts.length} fee line(s) drawn, one per line on the wire`,
  );
  console.log(`      lines: ${feeAmounts.map((one) => one.trim()).join(" · ")}`);
  const payAmount = await page.locator("[data-pay-amount]").getAttribute("data-pay-amount");
  check(
    payAmount === FEES_TO_PAY_NOW,
    `*to pay now* is ${payAmount} — ${FEES_TO_PAY_NOW} is $185.00 + $150.00, and the waived line is not in it`,
  );
  //: ⚠ **STRUCK THROUGH AND STILL LISTED** (TC-3). Asserted as a real `<s>`
  //: element rather than a class name, because a class that compiles to nothing
  //: is `DEF-974` and would leave the figure looking payable.
  const struck = page.locator("s[data-waived]");
  check((await struck.count()) === 1, "exactly one line is struck through");
  check(
    (await struck.innerText()).trim() === FEE_WAIVED,
    `…and it is the ${FEE_WAIVED} waiver, still on the list (US-CWP-050 TC-3)`,
  );
  const struckLine = await struck.evaluate((el) => getComputedStyle(el).textDecorationLine);
  check(
    struckLine.includes("line-through"),
    `…and the browser really paints it struck through (text-decoration-line: ${struckLine})`,
  );
  //: ⚠ **NO AMOUNT BOX AND NO PART PAYMENT** (TC-6) — a structural refusal
  //: rather than a validation message.
  check(
    (await page.locator('[data-screen="CWP-050"] input').count()) === 0,
    "there is no amount box on the screen at all — a part payment is refused structurally (TC-6)",
  );
  //: ⚠ **THE SECOND OF THE WAVE'S THREE SIGNED FIGURES HAS NEVER BEEN DRAWN.**
  gaps.known(
    fees.on_first_bill !== null && fees.on_first_bill !== undefined,
    "the deposit shows as its own row and its own total, on your first bill",
    {
      defect: "DEF-CWP-4176",
      why: "the seeded residential plan prices no deposit, so paying.py answers on_first_bill: null with deposit_not_priced and correctly refuses to draw a $0.00 — a zero would state a deposit was assessed and set to nothing. US-CWP-050 TC-4's middle figure is unproven rather than passing",
    },
  );

  const feesHold = await page.locator("[data-fees-hold]").getAttribute("data-fees-hold");
  check(
    feesHold === fees.held_reason,
    `the Pay control is held on \`${feesHold}\` — the server's reason, re-answered on every draw`,
  );
  await noInternals(page, "CWP-050");
  await page.screenshot({ path: join(OUT, "6-fees.png"), fullPage: true });

  // ═════ 7 · every hold drawn is a hold the register knows ═════════════════
  //: ⚠ `g103_holds_cannot_rot.py` fails a merge when a hold comes due — but it
  //: can only see a hold that has a ROW. A hold drawn with no row is invisible
  //: to it, which is the gap `DEF-CWP-4129` was filed for one screen over.
  console.log("\n── 7 · what a person is refused, and whether the register knows ──");
  const drawnHolds = [];
  for (const [screen, path, selector] of [
    ["CWP-038", "/pay-now", "[data-method-held]"],
    ["CWP-040", "/autopay", "[data-autopay-hold]"],
    ["CWP-050", "/fees", "[data-fees-hold]"],
  ]) {
    await page.goto(`${PORTAL}${path}`, { waitUntil: "networkidle" });
    await page.waitForSelector(`[data-screen="${screen}"]`, { timeout: 20000 });
    const count = await page.locator(selector).count();
    drawnHolds.push(`${screen} ${selector} → ${count}`);
  }
  console.log(`      ${drawnHolds.join(" · ")}`);
  check(true, "the three server-decided holds are the ones `PORTAL_HOLDS` registers as kind `server`");

  // ═════ what it cost, measured (11-response-times.md §5) ══════════════════
  await timings.report({
    targets: [
      { id: "RT-2", match: "/portal/auth/sign-in", p95: 900 },
      { id: "RT-5", match: "/pay-now/preview", p95: 900 },
    ],
  });

  await browser.close();
  //: ⚠ **`gaps.report` PRINTS THE COUNT EVEN ON A PASS, AND FAILS A GAP THAT HAS
  //: CLOSED.** `0 failures, 0 known gaps` and `0 failures, 2 known gaps` must
  //: never look the same to a reader.
  process.exit(gaps.report(failures));
})().catch((error) => {
  console.error(error);
  process.exit(2);
});

/**
 * Flip the sandbox provider's `behaviour` — the ONE place in this product where
 * *the gateway did not answer* is decided.
 *
 * ⚠ **THROUGH THE DATABASE AND NOT THROUGH `apps/payments`.** The behaviour is
 * a field on the tenant's `integration_connection` row, which is `integrations`'
 * own table; reaching into the payments module to fake an outcome would be
 * testing a mock rather than the product. This writes the same column a staff
 * user editing the connection would.
 *
 * Returns false — rather than throwing — when psql is unavailable, so the run
 * reports which step did not happen instead of dying halfway with five screens
 * unwalked.
 */
function setSandboxBehaviour(behaviour) {
  const url = process.env.DATABASE_URL;
  if (!url) {
    console.log("   (no DATABASE_URL — the timeout step needs it to flip the provider)");
    return false;
  }
  try {
    execFileSync("psql", [
      url,
      "-qAtc",
      `update integration_connection set config = jsonb_set(coalesce(config,'{}'::jsonb), '{behaviour}', '"${behaviour}"') where provider_key = 'payments_sandbox'`,
    ]);
    console.log(`      sandbox provider switched to \`${behaviour}\``);
    return true;
  } catch (error) {
    console.log(`   (could not switch the sandbox provider: ${String(error).slice(0, 120)})`);
    return false;
  }
}
