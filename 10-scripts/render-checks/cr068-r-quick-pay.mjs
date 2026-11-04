/**
 * RENDERED-OUTPUT CHECK — CR-068 wave R, "Quick pay for a guest", in a real browser.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: no gate in this repository looks at
 * rendered output, and nine defects in one day were found this way and by
 * nothing else. PO ruling 2026-09-03: *"ensure you do web walkthorugh before
 * you sign off the user story or build"*. Wave R shipped AS BUILT at `2.165.0`
 * on 2026-09-05 and its own `R4` stamp recorded that this file did not exist:
 * `CWP-003` and `CWP-004` were *"opened by nothing"*, while `CWP-002` was
 * reached only by the older `cwp_portal_walkthrough.mjs`.
 *
 * ⚠ **AND THIS WAVE IS MOSTLY ABOUT WHAT IS *NOT* THERE, WHICH IS THE HARDEST
 * THING TO CHECK.** `BR-CWP-019` is a rule about ABSENCE — a guest holding a
 * bill number and a postcode sees *"the amount owing and a masked name, and
 * nothing else about the account"*. An absence is invisible to every check this
 * repository has (hard rule 8's own lesson, `DEF-CUS-3653`). So the assertions
 * below are mostly negative and mostly taken **on the wire**, through
 * `page.request`, because that is where a leak would actually be: a field the
 * screen does not happen to render is still a field a stranger can read.
 *
 * ⚠ **THE TWO REFUSALS ARE COMPARED AS STRINGS, NOT INSPECTED.** *"A wrong
 * postcode and a non-existent bill number are refused byte-identically"* is the
 * whole security story of step 1 — a different message would confirm the bill
 * number exists — and the only way to check it is to hold both answers and
 * compare them. Reading each one and judging it *"looks the same"* is the check
 * that cannot fail.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   eval "$(10-scripts/proof-db.sh clone cwppr --export)"
 *   DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
 *     python3 06-backend/manage.py migrate && \
 *     python3 06-backend/manage.py seed_portal_demo
 *   (cd 06-backend && python3 manage.py shell < ../10-scripts/render-checks/cr068-pr-fixture.py)
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8147 --noreload &
 *   (cd 07-frontend && ./node_modules/.bin/vite build && \
 *      PORT=4347 API_PROXY_TARGET=http://127.0.0.1:8147 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4347 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr068-r-quick-pay.mjs
 *
 * ⚠ **BUILD THE BUNDLE BEFORE DRIVING IT.** `server.mjs` serves `dist/`; a
 * stale `dist/` makes every assertion below a statement about a build nobody is
 * shipping.
 *
 * ⚠ **THIS RUN CONSUMES ITS OWN FIXTURE — IT PAYS.** Step 3 settles the payable
 * bill, so that bill is `settled` afterwards and a second run against the same
 * database stops at step 0 saying so. That is the guard working, not a fault:
 * re-run `cr068-pr-fixture.py`, which picks the next payable bill, or clone the
 * database per run (`proof-db.sh clone` is 0.3s).
 *
 * ⚠ **AND THE LOCK STEP IS LAST, ON PURPOSE.** Step 6 deliberately burns five
 * wrong pairs to prove the fifteen-minute lockout, and the lock is keyed on the
 * CALLER'S ADDRESS. Run it earlier and every step after it is refused `locked`
 * — which would read as five broken screens.
 *
 * ⚠ **SO A SECOND RUN INSIDE FIFTEEN MINUTES STOPS AT STEP 0, AND THAT IS THE
 * LOCK WORKING.** It is held in Django's default cache, which under a bare
 * `runserver` is the per-process LocMem — so **restarting the backend clears
 * it**, and that is the whole reset. Do not read the refusal as a broken
 * lookup: step 0 stops the run rather than letting fifty assertions fail one
 * after another about a door this file shut itself.
 *
 * ── WHAT IT CLICKS (the wave R demo script, 10-execution-plan.md §Wave R) ──
 *   0  The state the demo script assumes, proved on the WIRE before a screen
 *      opens: the bill is really payable and really has that postcode.
 *   1  `CWP-002` — the pair off the paper finds the bill. A wrong postcode and
 *      a bill number that does not exist are refused **byte-identically**,
 *      compared as strings.
 *   2  `CWP-003` — *Billed to* is masked, fixed-width, and the served body
 *      carries **no other field of the customer record**; the *what this will
 *      do* box names the figure and the bill BEFORE the button (B14 rule 11).
 *   3  **Pay it.** One payment row, a reference, no account and no credential
 *      created — the last two asserted by trying to sign in afterwards.
 *   4  `CWP-004` — the reference, the amount, *card ending 8812*. Both receipt
 *      controls are HELD and each says so.
 *   5  A settled bill answers `$0.00` with **no Pay control** — not a refusal;
 *      a corrected bill directs payment at its replacement.
 *   6  Five wrong pairs → *locked for fifteen minutes*, and the amount is still
 *      not disclosed by the lock message.
 *   7  No card-fee line; nothing internal on any of the three screens
 *      (B14 rule 31 · rule 32).
 */

import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

import { Gaps } from "./lib/knownGaps.mjs";
import { attachTimings } from "./lib/timings.mjs";

const require = createRequire(join(process.cwd(), "07-frontend", "package.json"));
const { chromium } = require("playwright-core");

/** ⚠ `chromium.executablePath()` returns a path WITHOUT checking it exists, so
 *  a bare try/catch never fires and the launch dies on a version this machine
 *  does not have. `existsSync` is the check. */
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
  if (!found) throw new Error("no chromium on this machine — set PLAYWRIGHT_BROWSERS_PATH");
  return found;
}

const HANDOFF = process.env.SMOKE_HANDOFF ?? "/tmp/cr068-pr/fixture.json";
let handoff = {};
try {
  handoff = JSON.parse(readFileSync(HANDOFF, "utf8"));
} catch {
  handoff = {};
}

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4347";
const TENANT = process.env.SMOKE_TENANT ?? handoff.tenant ?? "pine-hill";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr068-r";
const VIEWPORT = { width: 1440, height: 1200 };

const PORTAL = `${BASE}/${TENANT}/portal`;
const PUBLIC = `${BASE}/api/${TENANT}/portal/public`;

const BILLS = handoff.bills ?? {};
/** A number ending 8812, so the receipt reads *card ending 8812* as the demo
 *  script does. `tokeniseCard` keeps the brand and the last four and nothing
 *  else; the digits never leave the browser. */
const CARD = "4111 1111 1111 8812";

mkdirSync(OUT, { recursive: true });

const failures = [];
const gaps = new Gaps();
let assertions = 0;

function check(ok, message) {
  assertions += 1;
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

function must(ok, message) {
  check(ok, message);
  if (!ok) {
    console.log("\n   STOPPED — the run cannot prove anything from here.");
    process.exit(1);
  }
}

//: ⚠ **THE LAST TWO ARE `DEF-CWP-4197` AND THEY ARE DELIBERATELY NOT PINNED TO
//: ONE SCREEN.** `CWP-004` printed `2026-09-06T03:59:13.769308+00:00` — a UTC
//: instant with microseconds — on the receipt somebody keeps, and `CWP-003`
//: printed the due date as `2026-08-22`, both while the tenant was publishing
//: `MM/DD/YYYY` and `America/Chicago` and both screens sat inside the provider
//: that carries them. Written as a pattern over the WHOLE BODY of every screen
//: this file opens, the check fails on the next portal screen that hand-rolls a
//: date too — which a pair of assertions naming `data-paid-at` could not.
//: ⚠ **EACH PATTERN CARRIES ITS OWN REASON, because they are not the same rule
//: and a message that says *(B14 rule 31)* over a date is a check whose output
//: misleads its reader** — law 7's third habit. Rule 31 is about database ids;
//: a raw ISO date is `DEF-CWP-4197`, a different fault with a different cure.
const FORBIDDEN = [
  [/\bBR-[A-Z]{3}-\d{3,5}\b/, "no rule id (B14 rule 31 · rule 32)"],
  [/\bOQ-(?:[A-Z]{3}-)?\d{3,5}\b/, "no open-question id (B14 rule 31 · rule 32)"],
  [/\bDEF-(?:[A-Z]{3}-)?\d{3,5}\b/, "no defect id (B14 rule 31 · rule 32)"],
  [/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/, "no database id (B14 rule 31)"],
  [/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/, "no raw machine instant (DEF-CWP-4197)"],
  [/\b\d{4}-\d{2}-\d{2}\b/, "no raw ISO date (DEF-CWP-4197)"],
];

async function noInternals(page, where) {
  const text = await page.locator("body").innerText();
  for (const [pattern, why] of FORBIDDEN) {
    check(!pattern.test(text), `${where}: ${why} on screen`);
  }
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  attachTimings(context);
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 160)}`);
  });
  console.log(`cr068-r: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);

  // ═════ 0 · the state the demo script assumes ═════════════════════════════
  console.log("\n── 0 · the bill this run pays, proved payable before a screen opens ──");
  const payable = BILLS.payable;
  must(
    payable !== undefined,
    `a payable bill in ${HANDOFF} — run cr068-pr-fixture.py first`,
  );
  const lookedUp = await context.request.post(`${PUBLIC}/bills/lookup`, {
    data: { bill_number: payable.number, postcode: payable.postcode },
  });
  must(lookedUp.ok(), `the pair ${payable.number} + ${payable.postcode} is accepted`);
  const found = await lookedUp.json();
  //: ⚠ **THE `DEF-WRK-4121` GUARD, and this run is the reason it is needed:
  //: step 3 PAYS, so on a second run against the same database this bill is
  //: `settled` and every screen below would draw its no-work state, greenly.**
  //: ⚠ **THE MESSAGE HAS TO READ CORRECTLY WHEN IT PASSES, NOT ONLY WHEN IT
  //: FAILS** (law 7's third habit — a check's output must distinguish pass from
  //: fail to a READER, not merely to an exit code). The first draft printed
  //: *"a previous run settled it; re-run the fixture"* beside a green tick.
  must(
    found.status === "payable",
    found.status === "payable"
      ? `the bill is \`payable\`, so this run has something to pay`
      : `the bill reads \`${found.status}\`, not \`payable\` — a previous run settled it; re-run cr068-pr-fixture.py`,
  );
  console.log(
    `      ${found.number}  ${found.amount.display}  (stored ${found.amount.amount})  billed to ${found.masked_name}`,
  );

  //: ⚠ **HARD RULE 2, ON THE WIRE.** Money is STORED to 4 decimals and
  //: DISPLAYED to 2, and this is the one place a guest sees both — the
  //: serialiser hands over `amount` and `display` side by side.
  check(
    /^\d+\.\d{4}$/.test(String(found.amount.amount)),
    `the stored figure carries FOUR decimals (${found.amount.amount}) — hard rule 2`,
  );
  check(
    /^\$\d[\d,]*\.\d{2}$/.test(String(found.amount.display)),
    `…and the displayed figure carries TWO (${found.amount.display})`,
  );
  check(found.amount.currency === "USD", `the currency is a CHAR(3) code (${found.amount.currency})`);

  //: **`BR-CWP-019` ON THE WIRE — the rule is about ABSENCE, so the check is a
  //: closed key set.** A field the screen does not render is still a field a
  //: stranger can read, which is why this is asserted here and not on the DOM.
  const allowed = ["number", "amount", "status", "due_on", "masked_name", "replaced_by"];
  const served = Object.keys(found).sort();
  check(
    JSON.stringify(served) === JSON.stringify([...allowed].sort()),
    `the body carries EXACTLY ${JSON.stringify(allowed.sort())} and nothing else — got ${JSON.stringify(served)}`,
  );
  //: The named absences, spelled out, because a key set is easy to widen by
  //: accident and these are the four that would matter.
  for (const leak of ["account_no", "account_id", "customer", "address", "premise", "email", "phone"]) {
    check(!(leak in found), `…no \`${leak}\` on a guest's answer`);
  }

  //: **THE MASK IS FIXED-WIDTH** (`US-CWP-004` TC-4) — a one-letter surname and
  //: a nine-letter surname must produce the same string, or the mask leaks the
  //: length of the name it is hiding.
  check(
    /^[A-Z]\. [A-Z]•{6}$/.test(found.masked_name),
    `the masked name is fixed-width — \`${found.masked_name}\` (initial, letter, six dots)`,
  );

  // ═════ 1 · CWP-002 — the pair off the paper, and the two identical refusals ═
  console.log("\n── 1 · find the bill, and the refusal that tells a stranger nothing ──");
  await page.goto(`${PORTAL}/pay`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-002"]', { timeout: 20000 });
  check(
    (await page.locator("[data-holding-screen]").count()) === 0,
    "CWP-002 is the real screen, not the holding screen its route shipped with",
  );

  //: ⚠ **COMPARED AS STRINGS.** Two refusals that "look the same" is not the
  //: assertion; byte-identity is.
  const wrongPostcode = await context.request.post(`${PUBLIC}/bills/lookup`, {
    data: { bill_number: payable.number, postcode: "00000" },
  });
  const noSuchBill = await context.request.post(`${PUBLIC}/bills/lookup`, {
    data: { bill_number: "BL-9999-999999", postcode: payable.postcode },
  });
  const wrongBody = await wrongPostcode.text();
  const missingBody = await noSuchBill.text();
  //: `trace_id` is per-request and is the ONE field that legitimately differs;
  //: everything else must match, so it is blanked on both sides rather than the
  //: comparison being loosened to a substring.
  const blank = (raw) => raw.replace(/"trace_id":"[^"]*"/, '"trace_id":"…"');
  check(
    blank(wrongBody) === blank(missingBody),
    "a REAL bill with the WRONG postcode and a bill that does not exist are refused BYTE-IDENTICALLY",
  );
  check(
    wrongPostcode.status() === noSuchBill.status(),
    `…including the status code (${wrongPostcode.status()} both)`,
  );
  console.log(`      both answer: ${blank(missingBody).slice(0, 160)}`);
  check(
    !blank(missingBody).includes(payable.number),
    "…and neither answer repeats the bill number back",
  );

  //: Now the correct pair, through the screen, as a person does it.
  await page.fill("#quickpay-number", payable.number);
  await page.fill("#quickpay-postcode", payable.postcode);
  await page.getByRole("button", { name: /continue/i }).click();
  await page.waitForSelector("[data-bill-found]", { timeout: 20000 });
  check(
    (await page.locator("[data-bill-number]").innerText()).trim() === payable.number,
    `the screen names the bill it found (${payable.number})`,
  );
  check(
    (await page.locator("[data-masked-name]").innerText()).trim() === found.masked_name,
    `…and the masked name on screen is the SERVER's (${found.masked_name}), not one the screen composed`,
  );
  await noInternals(page, "CWP-002");
  await page.screenshot({ path: join(OUT, "cwp-002-find.png"), fullPage: true });

  // ═════ 2 · CWP-003 — check and pay ═══════════════════════════════════════
  console.log("\n── 2 · check and pay: the figure and the bill, BEFORE the button ──");
  await page.getByRole("button", { name: new RegExp(`pay\\s*\\$`, "i") }).click();
  await page.waitForSelector('[data-screen="CWP-003"]', { timeout: 20000 });
  await page.waitForSelector("[data-bill-found]", { timeout: 20000 });
  check(
    (await page.locator("[data-no-handoff]").count()) === 0,
    "the pair travelled in router state — step 2 opened with the bill, not asking for it again",
  );
  //: ⚠ **AND THE ADDRESS CARRIES NEITHER FACT.** A bill number and somebody's
  //: postcode in a URL end up in access logs, in browser history and in a
  //: `Referer` header.
  const url = page.url();
  check(
    !url.includes(payable.number) && !url.includes(payable.postcode),
    `neither the bill number nor the postcode is in the address (${url})`,
  );

  //: **B14 rule 11 — any form that writes money shows a *what this will do* box
  //: before its commit button.** The two facts are asserted off the WRAPPER,
  //: because the sentence itself is the catalogue's (rule 35) and asserting the
  //: sentence would be asserting a translation.
  const consequence = page.locator("[data-pay-amount]");
  check((await consequence.count()) === 1, "the *what this will do* box is on the screen (B14 rule 11)");
  check(
    (await consequence.getAttribute("data-pay-amount")) === found.amount.display,
    `…and it names the figure ${found.amount.display}`,
  );
  check(
    (await consequence.getAttribute("data-pay-against")) === payable.number,
    `…and the bill it lands on (${payable.number})`,
  );
  //: ⚠ **THE THIRD PROMISE IS ASSERTED BY MEANING, NOT BY ITS SENTENCE.** The
  //: words are the catalogue's (B14 rule 35 — a catalogue is written in its own
  //: language, not translated from English), so pinning the exact string would
  //: assert a TRANSLATION and would go quiet in ten languages the day one of
  //: them was reworded. The first draft of this check pinned the WIREFRAME's
  //: wording — *"Does not create an account."* — and went red against a screen
  //: that correctly reads *"No account is created for you"*.
  const bullets = await consequence.locator("li").allInnerTexts();
  check(bullets.length === 3, `the box makes THREE promises (${bullets.length})`);
  check(
    bullets.some((one) => /account/i.test(one)),
    `…one of them about an account: "${bullets.find((one) => /account/i.test(one)) ?? "—"}"`,
  );

  //: `BR-CWP-057` — no card field ever reaches the server, and the screen is
  //: where that is visible: the digits are tokenised in the browser.
  check(
    (await page.locator("#quickpay-card").count()) === 1,
    "there is a card field to type into (the whole point of the screen)",
  );
  //: **The receipt-email box is GONE and the screen says so** (`DEF-CWP-3951`,
  //: hold `portal.quickPay.receiptEmailHeld`). It was accepted, validated and
  //: dropped — nothing sent to it, nothing checking that anything did.
  const emailHold = page.locator("[data-receipt-email-held]");
  check((await emailHold.count()) === 1, "the receipt-email refusal is STATED, not silent");
  const holdSentence = (await emailHold.innerText()).trim();
  console.log(`      it reads: "${holdSentence}"`);
  check(
    (await page.locator("input[type=email]").count()) === 0,
    "…and there is no email input to type an address nothing would send to",
  );

  await noInternals(page, "CWP-003");
  await page.screenshot({ path: join(OUT, "cwp-003-check.png"), fullPage: true });

  // ═════ 3 · pay it ════════════════════════════════════════════════════════
  console.log("\n── 3 · a stranger pays, and no account appears behind them ──");
  await page.fill("#quickpay-card", CARD);
  await page.fill("#quickpay-expires", "11/27");
  await page.fill("#quickpay-security", "123");
  await page.locator("[data-pay-control] button").click();
  await page.waitForSelector('[data-screen="CWP-004"]', { timeout: 30000 });

  const reference = (await page.locator("[data-reference]").innerText()).trim();
  check(reference.length > 0, `a reference to keep: ${reference}`);
  check(
    (await page.locator("[data-against]").innerText()).trim() === payable.number,
    `it says which bill it paid (${payable.number})`,
  );
  const receiptAmount = await page.locator("[data-receipt-amount]").getAttribute("data-receipt-amount");
  check(
    receiptAmount === found.amount.display,
    `and how much: ${receiptAmount} — the same figure the box promised`,
  );
  const lastFour = await page.locator("[data-last-four]").getAttribute("data-last-four");
  check(lastFour === "8812", `paid by card ending ${lastFour} (the digits never left the browser)`);

  //: ⚠ **THE ABSENCE OF AN ISO INSTANT IS NOT THE SAME AS A DATE BEING THERE.**
  //: The `noInternals` sweep below would pass just as happily over an EMPTY
  //: cell — which is the shape `usePortalDate` returns for a value it cannot
  //: read — so the positive half is asserted here: the server's own instant is
  //: still on the attribute, and something DIFFERENT and non-empty is drawn.
  //: Law 7's second habit: ask what would make this check pass wrongly.
  const paidCell = page.locator("[data-paid-at]");
  const paidRaw = await paidCell.getAttribute("data-paid-at");
  const paidShown = (await paidCell.innerText()).trim();
  check(paidShown.length > 0, `the paid date is DRAWN, not blank: "${paidShown}"`);
  check(
    paidShown !== paidRaw,
    `…and it is not the server's own string (${paidRaw}) — the tenant's format and zone (DEF-CWP-4197)`,
  );

  //: **THE BILL IS NOW SETTLED**, read back through the same public selector a
  //: stranger uses — which is also the proof the payment was allocated rather
  //: than merely recorded.
  const after = await (
    await context.request.post(`${PUBLIC}/bills/lookup`, {
      data: { bill_number: payable.number, postcode: payable.postcode },
    })
  ).json();
  check(
    after.status === "settled" && after.amount.display === "$0.00",
    `the bill now reads \`${after.status}\` and owes ${after.amount.display}`,
  );

  //: **NO ACCOUNT AND NO CREDENTIAL** (`US-CWP-004` TC-6, `US-CWP-005` TC-3).
  //: Asserted by trying to USE one: a credential minted silently would let this
  //: address sign in, and nothing else about the run would look different.
  const trySignIn = await context.request.post(`${BASE}/api/${TENANT}/portal/auth/sign-in`, {
    data: { email: `guest+${reference}@example.test`, password: "Pine-Hill-2026!" },
  });
  check(!trySignIn.ok(), `no credential was created behind the payment (sign-in ${trySignIn.status()})`);

  // ═════ 4 · CWP-004's two held controls ═══════════════════════════════════
  console.log("\n── 4 · the receipt, and the offer that is the point of this screen ──");
  //: ⚠ **THE DRAWING SHOWS BOTH CONTROLS WORKING AND BOTH ARE HELD**, each
  //: carrying `data-held-for` — which is what `BR-CWP-056` asks for: visible,
  //: disabled, and carrying its reason. Never hidden, never live-but-inert.
  const held = page.locator("[data-held-for]");
  const heldCount = await held.count();
  check(heldCount === 2, `both receipt controls are DRAWN and HELD (${heldCount})`);
  const heldFor = await held.evaluateAll((nodes) => nodes.map((n) => n.getAttribute("data-held-for")));
  console.log(`      held for: ${JSON.stringify(heldFor)}`);

  //: The enrolment offer — *"the single best moment in the whole product to
  //: offer an account, and the only one that costs nothing"*. `BR-CWP-029` and
  //: `PR-21`: offered LAST and never created silently.
  const offer = page.locator("[data-enrol-offer]");
  check((await offer.count()) === 1, "the *set up a login* offer is on the screen");
  const offerLink = offer.locator("a, button").first();
  const offerHref = await offerLink.getAttribute("href");
  //: ⚠ **ASSERTED BY ADDRESS, not by the words on the control** — the
  //: hold-expiry lesson (`DEF-CWP-3925`): a test that asserts a screen is
  //: registered somewhere while the router mounts it elsewhere passes over two
  //: screens that both say *not built yet*.
  check(
    typeof offerHref === "string" && offerHref.endsWith("/portal/enrol"),
    `…and it routes to the enrolment screen by ADDRESS (${offerHref})`,
  );

  await noInternals(page, "CWP-004");
  await page.screenshot({ path: join(OUT, "cwp-004-done.png"), fullPage: true });

  // ═════ 5 · the other three bill states ═══════════════════════════════════
  console.log("\n── 5 · a settled bill, and a corrected one ──");
  for (const [state, expectation] of [
    ["settled", "no Pay control, and NOT a refusal"],
    ["replaced", "directs payment at its replacement"],
  ]) {
    const one = BILLS[state];
    if (one === undefined) {
      check(false, `the fixture found no \`${state}\` bill to open`);
      continue;
    }
    await page.goto(`${PORTAL}/pay`, { waitUntil: "networkidle" });
    await page.fill("#quickpay-number", one.number);
    await page.fill("#quickpay-postcode", one.postcode);
    await page.getByRole("button", { name: /continue/i }).click();
    await page.waitForSelector("[data-bill-found]", { timeout: 20000 });
    const statusAttr = await page.locator("[data-bill-status]").getAttribute("data-bill-status");
    check(statusAttr === state, `${one.number} reads \`${statusAttr}\` — ${expectation}`);
    //: **NOT A REFUSAL.** A settled bill is not an error; it is a bill with
    //: nothing to pay, and the difference is what a person sees.
    check(
      (await page.locator("[data-quick-pay-refused]").count()) === 0,
      `…and it is NOT served as a refusal`,
    );
    check(
      (await page.locator("[data-nothing-to-pay]").count()) === 1,
      `…the screen says there is nothing to pay instead of offering a button`,
    );
    if (state === "replaced") {
      const replaced = page.locator("[data-replaced-by]");
      check(
        (await replaced.getAttribute("data-replaced-by")) === one.replaced_by,
        `…and it names the bill that replaced it (${one.replaced_by}) — BR-CWP-042`,
      );
    }
  }

  //: The fourth state. `bill_lookup` can answer `cancelled` for a VOID invoice
  //: and the seeded estate holds none — and this file will not mint one,
  //: because voiding an issued invoice is an UPDATE on an issued invoice and
  //: hard rule 4 forbids it outright. Recorded rather than asserted-and-ignored.
  gaps.known(
    BILLS.cancelled !== undefined,
    "demo step 4's fourth state — a VOIDED bill reads `cancelled`",
    {
      defect: "DEF-CWP-4196",
      why:
        "the seeded estate holds no void invoice, and a fixture cannot lawfully make one: voiding " +
        "an issued invoice is an UPDATE on an issued invoice, which hard rule 4 forbids. The " +
        "`cancelled` branch of `bill_lookup` therefore has unit coverage and has never been on a screen",
    },
  );

  // ═════ 6 · the lockout — LAST, because it locks this address ═════════════
  console.log("\n── 6 · five wrong pairs, and the door that closes ──");
  let lockedAt = 0;
  let lockMessage = "";
  for (let attempt = 1; attempt <= 6; attempt += 1) {
    const tried = await context.request.post(`${PUBLIC}/bills/lookup`, {
      data: { bill_number: `BL-0000-00000${attempt}`, postcode: "11111" },
    });
    const bodyText = await tried.text();
    if (/lock/i.test(bodyText)) {
      lockedAt = attempt;
      lockMessage = bodyText;
      break;
    }
  }
  //: ⚠ **EXACTLY SIX, NOT *"at most six"*.** `lockedAt > 0` would pass over a
  //: form that locked on the FIRST try, which is a broken form rather than a
  //: strict one, and `<= 6` would pass over the same thing — a check that
  //: cannot fail in the direction it matters. The screen promises *"after five
  //: wrong pairs"*, so five must be ALLOWED and the sixth must be REFUSED, and
  //: this run reaches step 6 with the counter at zero because every successful
  //: lookup before it clears the counter.
  check(
    lockedAt === 6,
    `five wrong pairs were allowed and the SIXTH was refused (closed on attempt ${lockedAt})`,
  );
  console.log(`      the lock answers: ${lockMessage.slice(0, 200)}`);
  //: **EVEN A CORRECT PAIR IS REFUSED INSIDE THE WINDOW**, which is what makes
  //: it a lockout rather than a delay (`US-CWP-002` TC-3).
  const correctWhileLocked = await context.request.post(`${PUBLIC}/bills/lookup`, {
    data: { bill_number: BILLS.settled.number, postcode: BILLS.settled.postcode },
  });
  const lockedBody = await correctWhileLocked.text();
  check(
    /lock/i.test(lockedBody),
    "a CORRECT pair inside the window is refused too — a lockout, not a delay",
  );
  check(
    !lockedBody.includes("$"),
    "…and the lock message discloses no figure",
  );

  console.log(`\n   ${assertions} assertion(s) ran.`);
  console.log(`   screenshots in ${OUT}`);
  await browser.close();
  process.exit(gaps.report(failures));
})().catch((error) => {
  console.error("\n⛔ the walkthrough itself broke:", error);
  process.exit(1);
});
