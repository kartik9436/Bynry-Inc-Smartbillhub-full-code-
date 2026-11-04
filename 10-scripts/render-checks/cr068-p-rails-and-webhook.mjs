/**
 * RENDERED-OUTPUT CHECK — CR-068 wave P, "Rails and the webhook", in a real browser.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: no gate in this repository looks at
 * rendered output, and nine defects in one day were found this way and by
 * nothing else. PO ruling 2026-09-03: *"ensure you do web walkthorugh before
 * you sign off the user story or build"*. Wave P shipped AS BUILT at `2.165.0`
 * on 2026-09-05 and its own `P5` stamp recorded that this file did not exist —
 * so `CWP-039` had unit tests, DOM tests and an endpoint contract, and nobody
 * had opened it.
 *
 * ⚠ **AND THE OTHER HALF OF THIS WAVE IS NOT A SCREEN AT ALL.** Hard rule 6 —
 * *bill runs and inbound payment webhooks are idempotent* — is the wave's
 * headline promise, and it is the one claim in the portal that costs a customer
 * real money when it is wrong: a duplicate settlement is money they did not pay
 * sitting on their account, which the allocation engine then spends on their
 * next bill. So the middle of this file is not a browser at all. It posts real
 * signed deliveries at the mounted endpoint against a real PostgreSQL and
 * **prints what it sent, what came back, and the row count before and after
 * each one.**
 *
 * ── THE FOUR-DELIVERY SHAPE, AND WHY DELIVERY 3 IS THE ONLY ONE THAT MATTERS ─
 *
 * *"I sent it twice and no second row appeared"* is worth **nothing** on its
 * own. An endpoint that is inert, throttled, misconfigured, unmounted or
 * refusing everything for an unrelated reason produces exactly that
 * observation, and a walkthrough that stopped there would be reporting a shut
 * door as a working guard — hard-won law 7's *"ask what would make this check
 * pass wrongly"*, and the specific way this one passes wrongly.
 *
 * So delivery 3 re-sends **the same money under a new event id and REQUIRES a
 * second row.** Only then is delivery 2's silence the dedupe rather than the
 * door. Delivery 4 forges a signature to show the refusal path is real and is
 * not what delivery 2 was measuring, and delivery 5 aims at a provider this
 * deployment holds no secret for, so *fails closed* is a passing assertion
 * rather than a paragraph.
 *
 * ⚠ **THIS WAS PROVED INDEPENDENTLY OF WAVE Q, NOT BY CITING IT.** The sibling
 * lane reported *"I could not make a payment webhook apply twice"* for wave Q
 * and its four deliveries are the same shape. This file re-derives the answer
 * against its own stack, its own tenant and its own event ids, and adds two
 * dimensions Q does not print: **the delivery-row count beside the payment-row
 * count** (a replay writes NEITHER; a refusal writes a delivery row and no
 * payment — which is the whole reason `payment_webhook_events` exists), and a
 * **concurrent** pair, which is the case guard 1's SELECT cannot close and only
 * the unique index can.
 *
 * ── ⚠ THE SECRET, AND WHY A STOCK SERVER PROVES NOTHING HERE (DEF-PAY-4188) ─
 *
 * `signing_secret` reads `settings.PAYMENT_WEBHOOK_SECRETS`, and **the word
 * WEBHOOK appears nowhere in `config/settings/` or in `.env.example`** — there
 * is no `env.dict`/`env.json` reader in the settings package at all. So on
 * every server in this repository the endpoint answers every delivery
 * `no_signing_secret_configured`, and a walkthrough posting at it would observe
 * *"no second payment row"* from an endpoint that creates no FIRST one either.
 * The empty default is CORRECT and signed (decision log 2026-09-03, hard-won
 * law 3 — the unsafe option must be the one you type); what is missing is the
 * way to type it, which is `DEF-PAY-4188`.
 *
 * **This file therefore takes `SMOKE_WEBHOOK_SECRET`, and without it SKIPS
 * LOUDLY with the count of assertions that did not run** — because a declared
 * blind spot with no number attached is indistinguishable from an empty one
 * (law 7's fifth shape). To run those assertions, start the server with a
 * settings module that sets the mapping. ⚠ **Do NOT edit a repo file to do
 * it:** put a shim on `PYTHONPATH` outside the tree, so that no product file is
 * changed in order to make a proof pass.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   eval "$(10-scripts/proof-db.sh clone cwppr --export)"
 *   DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
 *     python3 06-backend/manage.py migrate && \
 *     python3 06-backend/manage.py seed_portal_demo
 *   (cd 06-backend && python3 manage.py shell < ../10-scripts/render-checks/cr068-pr-fixture.py)
 *
 *   # the walkthrough's own settings shim, OUTSIDE the repo:
 *   #   /tmp/<lane>/proofsettings/webhook_local.py
 *   #     from config.settings.local import *
 *   #     PAYMENT_WEBHOOK_SECRETS = {"payments_sandbox": os.environ["SMOKE_WEBHOOK_SECRET"]}
 *   PYTHONPATH=/tmp/<lane>:06-backend DJANGO_SETTINGS_MODULE=proofsettings.webhook_local \
 *     JOBS_EAGER=false SMOKE_WEBHOOK_SECRET=<a secret> \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8147 --noreload &
 *   (cd 07-frontend && ./node_modules/.bin/vite build && \
 *      PORT=4347 API_PROXY_TARGET=http://127.0.0.1:8147 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4347 SMOKE_WEBHOOK_SECRET=<the same secret> \
 *     PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr068-p-rails-and-webhook.mjs
 *
 * ⚠ **BUILD THE BUNDLE BEFORE DRIVING IT.** `server.mjs` serves `dist/`. A
 * stale `dist/` means every assertion below passes or fails about a build
 * nobody is shipping — a check that cannot fail, wearing a green tick.
 *
 * ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** A mid-run reseed
 * looks exactly like a broken screen.
 *
 * ⚠ **AND RUN THE FIXTURE, OR THIS PROVES ALMOST NOTHING.** `seed_portal_demo`
 * leaves the tenant with **no stored instruments and no payments provider**, so
 * `CWP-039` draws its EMPTY state and the run is green having never seen the
 * masked method string the whole story is about. That is `DEF-WRK-4121`'s exact
 * shape — a dispatcher that could not raise a work order on any non-empty list,
 * because every test used the empty one. **Step 0 asserts the state is really
 * there and stops the run if it is not.**
 *
 * ── WHAT IT DOES (the wave P demo script, 10-execution-plan.md §Wave P) ────
 *   0  The state the demo script assumes, proved on the WIRE first: the
 *      provider is connected, two instruments are saved, the login works.
 *   1  `CWP-039` in a browser — the two rows read `Chase ••••4021` and
 *      `Visa ••••8812 · expires 11/27`, and **no run of five or more digits
 *      appears anywhere in the DOM or anywhere in the served body**, which is
 *      how `BR-CWP-057` is checked rather than asserted.
 *   2  Step-up (`BR-CWP-040`): saving a method with **no** code is refused at
 *      the ENDPOINT, not merely disabled on the screen; and the refusal is a
 *      CODE, carrying nothing that was sent.
 *   3  The webhook, five deliveries, with the row counts printed either side.
 *   4  The two guards are separate (`DEF-058`): a **concurrent** identical pair
 *      leaves one payment, which is the case guard 1's SELECT cannot close.
 *   5  **The savepoint, on PostgreSQL** (law 14): a delivery whose PAYMENT is
 *      refused must still leave its delivery row. Without the nested
 *      `transaction.atomic()` the row is lost precisely on the deliveries that
 *      most needed recording — and SQLite, which the test suite runs on, has no
 *      aborted-transaction state, so the broken version passes every test.
 *   6  Demo-script step 6, the reversal — recorded as a KNOWN GAP against
 *      `DEF-PAY-4189`, because what the product does is not *"not built"*.
 *   7  Nothing on this screen shows a database id or an internal code
 *      (B14 rule 31 · rule 32), and no card-fee line is drawn.
 */

import { execFileSync } from "node:child_process";
import { createHmac } from "node:crypto";
import { existsSync, mkdirSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

import { Gaps } from "./lib/knownGaps.mjs";
import { attachTimings } from "./lib/timings.mjs";

const require = createRequire(join(process.cwd(), "07-frontend", "package.json"));
const { chromium } = require("playwright-core");

/** ⚠ `chromium.executablePath()` RETURNS A PATH WITHOUT CHECKING IT EXISTS, so
 *  a bare try/catch never fires and the launch dies on a version this machine
 *  does not have. `existsSync` is the check; wave Q found this first. */
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
const EMAIL = process.env.SMOKE_EMAIL ?? handoff.email;
const PASSWORD = process.env.SMOKE_PASSWORD ?? handoff.password ?? "Pine-Hill-2026!";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr068-p";
const VIEWPORT = { width: 1440, height: 1100 };

const PORTAL = `${BASE}/${TENANT}/portal`;
const API = `${BASE}/api/${TENANT}/portal`;
const PROVIDER = "payments_sandbox";
const WEBHOOK_SECRET = process.env.SMOKE_WEBHOOK_SECRET ?? "";

/** The wireframe's own two rows (`wireframes/CWP-039.png`). */
const BANK_LABEL = "Chase ••••4021";
const CARD_LABEL = "Visa ••••8812";

mkdirSync(OUT, { recursive: true });

const failures = [];
const gaps = new Gaps();
let assertions = 0;

function check(ok, message) {
  assertions += 1;
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

/** A precondition. If this is wrong nothing below means anything, so it stops. */
function must(ok, message) {
  check(ok, message);
  if (!ok) {
    console.log("\n   STOPPED — the run cannot prove anything from here.");
    process.exit(1);
  }
}

/** Never an id, never an internal code, and never a machine date, on screen.
 *  ⚠ **EACH PATTERN CARRIES ITS OWN REASON** — they are not the same rule, and
 *  a message reading *(B14 rule 31)* over a date is a check whose output
 *  misleads its reader (law 7's third habit). The two date patterns are
 *  `DEF-CWP-4197`: `CWP-039`'s ADDED column printed `2026-09-06` where the
 *  drawing reads *4 Mar 2026*, while the tenant was publishing `MM/DD/YYYY`. */
const FORBIDDEN = [
  [/\bBR-[A-Z]{3}-\d{3,5}\b/, "no rule id (B14 rule 31 · rule 32)"],
  [/\bOQ-(?:[A-Z]{3}-)?\d{3,5}\b/, "no open-question id (B14 rule 31 · rule 32)"],
  [/\bDEF-(?:[A-Z]{3}-)?\d{3,5}\b/, "no defect id (B14 rule 31 · rule 32)"],
  [/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/, "no database id (B14 rule 31)"],
  [/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/, "no raw machine instant (DEF-CWP-4197)"],
  [/\b\d{4}-\d{2}-\d{2}\b/, "no raw ISO date (DEF-CWP-4197)"],
];

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  attachTimings(context);
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 160)}`);
  });
  console.log(`cr068-p: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);

  // ═════ 0 · the state the demo script assumes ═════════════════════════════
  //: ⚠ Asserted on the WIRE before a screen opens. A screen that failed to DRAW
  //: a saved card and a database that HOLDS no saved card look identical in a
  //: browser, and they are opposite faults.
  console.log("\n── 0 · the state wave P's screen needs, proved before it is used ──");
  must(
    typeof EMAIL === "string" && EMAIL.length > 0,
    `a login to walk as (from ${HANDOFF}, or SMOKE_EMAIL) — run cr068-pr-fixture.py first`,
  );
  const signIn = await context.request.post(`${API}/auth/sign-in`, {
    data: { email: EMAIL, password: PASSWORD },
  });
  must(signIn.ok(), `signed in as ${EMAIL}`);

  const listed = await (await context.request.get(`${API}/payment-methods`)).json();
  const methods = listed.methods ?? [];
  //: **THE `DEF-WRK-4121` GUARD.** Both of these were ABSENT on a plain
  //: `seed_portal_demo` database, and the screen's empty state is green.
  must(methods.length >= 2, `${methods.length} saved method(s) — the screen has rows to draw`);
  console.log(`      served keys: ${Object.keys(methods[0]).join(", ")}`);

  // ═════ 1 · CWP-039 — the masked string, and the digits that are not there ═
  console.log("\n── 1 · your payment methods, in a browser ──");
  await page.goto(`${PORTAL}/sign-in`, { waitUntil: "networkidle" });
  await page.fill("#portal-email", EMAIL);
  await page.fill("#portal-password", PASSWORD);
  await page.getByRole("button", { name: /sign in/i }).click();
  await page.waitForSelector('[data-portal-frame="shell"]', { timeout: 20000 });

  await page.goto(`${PORTAL}/payment-methods`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-039"]', { timeout: 20000 });
  check(
    (await page.locator("[data-holding-screen]").count()) === 0,
    "the screen is the real one, not the holding screen its route shipped with",
  );

  const screenText = await page.locator('[data-screen="CWP-039"]').innerText();
  check(screenText.includes(BANK_LABEL), `the bank row reads \`${BANK_LABEL}\``);
  check(screenText.includes(CARD_LABEL), `the card row reads \`${CARD_LABEL}\``);
  check(
    /expires\s*11\/27/i.test(screenText),
    "…and the card says when it expires (`expires 11/27`)",
  );

  //: ⚠ **`BR-CWP-057` IS CHECKED, NOT ASSERTED.** The rule is that a stored
  //: instrument is a token, a brand and a last four — *"no column holds more
  //: than four digits of a card"*. The way to check that from outside is to
  //: look for what must NOT be there: any run of five or more digits, in the
  //: DOM and in the served body. A `toContain("8812")` would pass just as
  //: happily over a screen printing the whole number.
  const bodyText = await page.locator("body").innerText();
  const longRunsOnScreen = bodyText.match(/\d{5,}/g) ?? [];
  check(
    longRunsOnScreen.length === 0,
    `no run of 5+ digits anywhere in the DOM${
      longRunsOnScreen.length ? ` — found ${JSON.stringify(longRunsOnScreen.slice(0, 4))}` : ""
    }`,
  );
  const servedRaw = JSON.stringify(listed);
  const longRunsOnWire = servedRaw.match(/\d{5,}/g) ?? [];
  check(
    longRunsOnWire.length === 0,
    `…and none in the served body either${
      longRunsOnWire.length ? ` — found ${JSON.stringify(longRunsOnWire.slice(0, 4))}` : ""
    }`,
  );
  check(
    !("gateway_token" in (methods[0] ?? {})),
    "no `gateway_token` leaves the edge (the served row's keys are a closed set)",
  );

  //: The note is a DESIGN REQUIREMENT and not reassurance copy (`US-CWP-046`
  //: §1, in as many words): it is on screen because it is true of the SCHEMA.
  check(
    /never hold your full card number/i.test(screenText),
    "the note about the token is on the screen, not only in the docstring",
  );

  //: `BR-CWP-056` — a refused control is VISIBLE, DISABLED and carries its
  //: reason. Never hidden, never live-but-inert. This is hard-won law 2's
  //: mirror: the thing G13 cannot see.
  const addButton = page.locator("[data-add-method]");
  check((await addButton.count()) === 1, "*Add a method* is DRAWN (BR-CWP-056)");

  //: ⚠ **THE TABLE DRAWS WHAT THE SERVER SERVED — NO MORE AND NO FEWER.**
  //: Written as `>= 2` this would pass over a table showing the same card FOUR
  //: times, which is exactly what a run of this walkthrough produced when the
  //: fixture's idempotency key changed shape underneath it. A row count that
  //: only has a floor cannot see a duplicate, and a duplicated saved card on a
  //: payment screen is the kind of thing a customer rings up about.
  const drawnRows = await page.locator("[data-row]").count();
  check(
    drawnRows === methods.length,
    `the table draws ${drawnRows} row(s), exactly what the server served (${methods.length})`,
  );

  await page.screenshot({ path: join(OUT, "cwp-039-methods.png"), fullPage: true });

  // ═════ 2 · step-up — refused at the ENDPOINT, not merely on the screen ════
  //: ⚠ **A SCREEN THAT MERELY DISABLES A CONTROL IS DEFEATED BY CALLING THE
  //: CONTROL DIRECTLY**, which is the whole reason this assertion goes through
  //: `page.request` and not through a click. `BR-CWP-040`.
  console.log("\n── 2 · a stored method may not change without a fresh code ──");
  const noCode = await context.request.post(`${API}/payment-methods`, {
    data: { reference: "tok_test_cr068p_walkthrough" },
  });
  const noCodeBody = await noCode.json().catch(() => ({}));
  check(
    !noCode.ok(),
    `saving a method with NO step-up code is refused at the endpoint (HTTP ${noCode.status()})`,
  );
  const refusalText = JSON.stringify(noCodeBody);
  check(
    !/tok_test_cr068p_walkthrough/.test(refusalText),
    "…and the refusal carries NOTHING that was sent (a refusal that echoed the field would put a card number in a proxy log)",
  );
  console.log(`      answered ${refusalText.slice(0, 200)}`);

  // ═════ 3 · CAN AN INBOUND WEBHOOK BE MADE TO APPLY TWICE? ════════════════
  console.log("\n── 3 · the same settlement twice, and the control that proves it ──");
  const accountId = handoff.account_id;
  let webhookAssertions = 0;
  if (WEBHOOK_SECRET === "" || !accountId) {
    console.log("   ⏭  SKIPPED — no SMOKE_WEBHOOK_SECRET, so the endpoint refuses every");
    console.log("      delivery `no_signing_secret_configured` (DEF-PAY-4188) and 9 assertions");
    console.log("      about idempotency, the savepoint and fail-closed did NOT run.");
    console.log("      Start the server with PAYMENT_WEBHOOK_SECRETS set — see the header.");
  } else {
    const hook = (provider) => `${BASE}/api/${TENANT}/portal/webhooks/payments/${provider}`;
    const stamp = Date.now();
    const settlement = (eventId, extra = {}) => ({
      id: eventId,
      type: "charge.settled",
      account_id: accountId,
      amount: "25.00",
      currency: "USD",
      posted_at: "2026-09-06T09:00:00Z",
      cleared_at: "2026-09-06T09:00:00Z",
      reference: eventId,
      ...extra,
    });

    //: ⚠ **SIGNED OVER THE BYTES THAT ARE SENT, never over a re-serialised
    //: object.** Two JSON encoders disagree about spacing and key order, so a
    //: signature computed over anything but the exact payload fails for a
    //: reason nobody can debug — and that debugging usually ends with somebody
    //: switching verification off.
    const deliver = async (body, { forge = false, provider = PROVIDER } = {}) => {
      const raw = JSON.stringify(body);
      const mac = createHmac("sha256", WEBHOOK_SECRET).update(raw).digest("hex");
      const answer = await context.request.post(hook(provider), {
        data: raw,
        headers: {
          "Content-Type": "application/json",
          "X-Signature": `sha256=${forge ? "0".repeat(64) : mac}`,
        },
      });
      return { raw, body: await answer.json() };
    };

    //: ⚠ **BOTH COUNTS, EVERY TIME.** The payment count answers *did money land
    //: twice*; the delivery count answers *was the delivery RECORDED* — and
    //: they move differently on purpose. A replay writes neither. A refusal
    //: writes a delivery row and no payment, which is the entire reason
    //: `payment_webhook_events` exists: without a row, a provider
    //: misconfiguration and an attack look identical in an empty log.
    const counts = async () => {
      const money = await (await context.request.get(`${API}/payments`)).json();
      //: ⚠ **THE LIST BODY'S KEY IS `money`, NOT `payments`** — written the
      //: other way it is `[]` for a body that does not carry that key, so the
      //: count reads 0 before AND after a payment that really was written.
      if (!Array.isArray(money.money)) {
        throw new Error(`the money list has no \`money\` array (keys: ${Object.keys(money)})`);
      }
      return money.money.length;
    };

    const wch = (ok, message) => {
      webhookAssertions += 1;
      check(ok, message);
    };

    const c0 = await counts();
    const d1 = await deliver(settlement(`STL-P-${stamp}-01`));
    const c1 = await counts();
    console.log(`      sent     ${d1.raw}`);
    console.log(`      answered ${JSON.stringify(d1.body.status)} verified=${d1.body.signature_verified}`);
    wch(c1 === c0 + 1, `one signed settlement wrote ONE payment row (${c0} → ${c1})`);

    const d2 = await deliver(settlement(`STL-P-${stamp}-01`));
    const c2 = await counts();
    console.log(`      re-sent  the identical body, same event id`);
    console.log(`      answered ${JSON.stringify(d2.body.status)}`);
    wch(c2 === c1, `the SAME event id again wrote NOTHING (${c1} → ${c2}) — hard rule 6`);
    wch(
      String(d2.body.status ?? "").toLowerCase() === "duplicate",
      `…and was RECOGNISED as a replay rather than refused for some other reason: status=${JSON.stringify(d2.body.status)}`,
    );

    //: ═══ THE CONTROL. Without this line, everything above is also true of a
    //: door that is simply shut.
    const d3 = await deliver(settlement(`STL-P-${stamp}-02`));
    const c3 = await counts();
    wch(
      c3 === c2 + 1 && String(d3.body.status ?? "") === "accepted",
      `the SAME money under a DIFFERENT event id DID write a second row (${c2} → ${c3}) — so the silence above is the dedupe, not a shut door`,
    );

    const d4 = await deliver(settlement(`STL-P-${stamp}-03`), { forge: true });
    const c4 = await counts();
    wch(
      c4 === c3 && d4.body.signature_verified === false,
      `a FORGED signature wrote nothing (${c3} → ${c4}) and was refused by name: ${JSON.stringify(
        (d4.body.problems ?? []).map((p) => p.code),
      )}`,
    );

    //: **FAILS CLOSED, as a passing assertion rather than as a paragraph**
    //: (hard-won law 3). This deployment holds a secret for `payments_sandbox`
    //: and for nothing else, so a delivery aimed anywhere else is refused for
    //: the absence of a secret — which is what a stock server does to EVERY
    //: delivery (`DEF-PAY-4188`).
    const d5 = await deliver(settlement(`STL-P-${stamp}-04`), { provider: "worldpay" });
    const c5 = await counts();
    const d5codes = (d5.body.problems ?? []).map((p) => p.code);
    wch(
      c5 === c4 && d5codes.includes("no_signing_secret_configured"),
      `a provider this deployment has NO secret for is refused by name (${c4} → ${c5}): ${JSON.stringify(d5codes)}`,
    );

    // ═════ 4 · the two guards are separate (DEF-058) ═══════════════════════
    //: `DEF-058`: a lane once switched guard 1 off to prove it bites, and
    //: NOTHING went red — the unique index caught the duplicate one layer down
    //: and the observable behaviour was identical. So the concurrent case is
    //: asserted on its own: two identical deliveries in flight at once is the
    //: race guard 1's pre-insert SELECT cannot close, and only
    //: `uq_payment_webhook_events_event` can.
    console.log("\n── 4 · the same delivery twice AT ONCE — the race the SELECT cannot close ──");
    const before = await counts();
    const raced = await Promise.all([
      deliver(settlement(`STL-P-${stamp}-05`)),
      deliver(settlement(`STL-P-${stamp}-05`)),
    ]);
    const after = await counts();
    const statuses = raced.map((one) => one.body.status);
    wch(
      after === before + 1,
      `two CONCURRENT identical deliveries left ONE payment (${before} → ${after}); answers were ${JSON.stringify(statuses)}`,
    );

    // ═════ 5 · the savepoint, on PostgreSQL (hard-won law 14) ══════════════
    //: ⚠ **THE SUITE RUNS ON SQLITE AND CANNOT SEE THIS.** `config/settings/
    //: test.py` hardcodes in-memory SQLite, which has no aborted-transaction
    //: state, so a version with no nested `transaction.atomic()` passes every
    //: test on every machine and loses the delivery row on the first real
    //: refusal in production. The delivery row is written and THEN the payment
    //: is attempted; if the payment fails and the failure is not contained in a
    //: SAVEPOINT, PostgreSQL aborts the whole transaction and **the row is lost
    //: precisely on the deliveries that most needed recording.**
    console.log("\n── 5 · a delivery whose PAYMENT fails must still leave its row (law 14) ──");
    const spBefore = await counts();
    const noSuchAccount = "01a074be-dead-7000-8000-000000000000";
    const sp = await deliver(
      settlement(`STL-P-${stamp}-06`, { account_id: noSuchAccount }),
    );
    const spAfter = await counts();
    const spCodes = (sp.body.problems ?? []).map((p) => p.code);
    wch(
      spAfter === spBefore && String(sp.body.status) === "refused",
      `a settlement for an account this tenant does not have wrote NO payment (${spBefore} → ${spAfter})`,
    );
    wch(
      sp.body.created === true,
      "…and the DELIVERY row was still committed (`created: true`) — the savepoint holding, on PostgreSQL",
    );
    wch(
      spCodes.includes("refused_by_a_payment_rule") && !spCodes.some((c) => /not an account of/.test(String(c))),
      `…and the reason travels as a CODE and not as a sentence naming the caller's own id: ${JSON.stringify(spCodes)}`,
    );

    // ═════ 6 · demo-script step 6 — the reversal ════════════════════════════
    //: The plan asks for *"a reversal … → two rows, the payment and the
    //: reversal above it — not mistaken for a duplicate"*. It is not mistaken
    //: for a duplicate. It is mistaken for a PAYMENT, which is worse, and that
    //: is `DEF-PAY-4189`. Recorded as a known gap rather than asserted-and-
    //: ignored: this run goes RED the day the branch is added and this row is
    //: still here.
    console.log("\n── 6 · demo step 6, the reversal ──");
    const rvBefore = await counts();
    const rv = await deliver(settlement(`STL-P-${stamp}-07`, { type: "charge.reversed" }));
    const rvAfter = await counts();
    console.log(`      sent a signed \`charge.reversed\` for 25.00 → ${JSON.stringify(rv.body.status)}`);
    console.log(`      payments ${rvBefore} → ${rvAfter}`);
    gaps.known(
      rvAfter === rvBefore,
      "a non-settlement event writes no payment row",
      {
        defect: "DEF-PAY-4189",
        why:
          "`event_type` is stored on the delivery row and branched on nowhere; `CHARGE_SETTLED` is " +
          "compared against nothing on the inbound path, so a signed `charge.reversed` for 25.00 is " +
          "ACCEPTED and recorded as a positive 25.00 payment — money the processor is taking back, " +
          "booked as money arriving",
      },
    );
  }

  // ═════ 7 · nothing internal on the screen ════════════════════════════════
  console.log("\n── 7 · B14 rule 31 · rule 32, and no fee line ──");
  await page.goto(`${PORTAL}/payment-methods`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-039"]', { timeout: 20000 });
  const finalText = await page.locator("body").innerText();
  for (const [pattern, why] of FORBIDDEN) {
    check(!pattern.test(finalText), `${why} on screen`);
  }
  //: `OQ-1394` CLOSED 2026-09-04 — BOTH options behind a per-tenant switch. The
  //: beta ships ABSORBED, so the screen states the utility's STANCE and **never
  //: a figure**: pricing a surcharge needs a processor's own schedule and there
  //: is no processor. There is no `NotImplementedError` here and the plan's
  //: table is superseded on that point — see wave P's AS BUILT stamp.
  //:
  //: ⚠ **THE FIRST DRAFT OF THIS CHECK ASSERTED THE WORDS *card fee* WERE
  //: ABSENT, AND IT WENT RED ON A CORRECT SCREEN.** The rule is not that fees
  //: are unmentionable — the wave's line is *"no fee line is drawn"*, i.e. no
  //: fee is PRICED. A screen silent about fees would be worse, not better. The
  //: check is therefore: the stance is stated, and it carries no money.
  const feeStance = page.locator("[data-card-fee]");
  check((await feeStance.count()) === 1, "the utility's card-fee stance is STATED, not omitted");
  const feeText = (await feeStance.innerText()).trim();
  console.log(`      the stance reads: "${feeText}" (payer=${await feeStance.getAttribute("data-card-fee")})`);
  check(
    !/[$£€]\s*\d/.test(feeText),
    "…and it names no figure (OQ-1394 closed 2026-09-04: beta absorbs, nothing is priced)",
  );

  await page.screenshot({ path: join(OUT, "cwp-039-final.png"), fullPage: true });

  console.log(`\n   ${assertions} assertion(s) ran; ${webhookAssertions} of them about the webhook.`);
  console.log(`   screenshots in ${OUT}`);
  await browser.close();
  process.exit(gaps.report(failures));
})().catch((error) => {
  console.error("\n⛔ the walkthrough itself broke:", error);
  process.exit(1);
});
