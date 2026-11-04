// ── Trace ────────────────────────────────────────────────────────────────────
// Ask:      PO, 2026-09-20, verbatim: *"The other half of the job. Today a
//           utility can cut supply and cannot restore it from the product."*
//           and *"The register reflects reality. Today a failed visit is
//           invisible and the case looks untouched."*
// Walks:    `/{t}/disconnects/{case}` — the case record's two NEW commits:
//           `Mark reconnecting` → `Restore service`, and `Record visit`.
// Rules:    BR-CUS-1083 (the four crew outcomes and where each sends the case)
//           · BR-PAY-036 (a payment never auto-restores; restoration is an
//           explicit, audited staff act) · BR-CUS-104 (the fee is owed AT the
//           cut) · BR-SHL-025 (a refused control renders disabled WITH ITS
//           REASON) · B14 rules 6, 31, 33 · CLAUDE.md hard-won laws 2 and 6
// ─────────────────────────────────────────────────────────────────────────────
//
// ⚠ **THIS IS A PERSON WITH A BROWSER, WHICH IS THE ONLY CHECK IN THIS REPO
// THAT READS RENDERED OUTPUT** (hard-won law 6). It drives the SHIPPED bundle
// through a real router, a real query client, a real API and a real PostgreSQL
// with RLS on.
//
// ⚠ **IT WRITES, AND THE WRITES ARE GATED AND NAMED.**
//   * read-only by default: it opens both records and asserts what is offered.
//   * `RWALK_RECONNECT=1` takes a real payment on `RWALK_ACCT`, then presses
//     `Mark reconnecting` and `Restore service`. **The restoration cannot be
//     undone from the product** — the case leaves the register for ever.
//   * `RWALK_VISIT=1` records a crew outcome on `RWALK_VISIT_CASE`. That
//     clears the cut date and moves the case; it is re-schedulable afterwards.
//
// ⚠ **THE LADDER RUNGS STILL HAVE NO SCREEN**, which is the remaining half of
// this module's door debt: `open_case`, `advance`, `record_notice`,
// `record_proof_of_service` and `lift_protection` are mounted and reachable
// from no page. So `--arm` drives those five through their own HTTP doors, with
// the browser's signed-in session, purely to put a case in the state a crew
// would be dispatched against. **The acts under test are pressed in the
// browser, never posted.**
//
//   node 10-scripts/po20260920_reconnect_and_visit_walk.mjs
//   RWALK_RECONNECT=1 node …
//   RWALK_VISIT=1 RWALK_ARM=1 node …
//
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..");
const require = createRequire(path.join(ROOT, "07-frontend/package.json"));
const { chromium } = require("playwright");

const BASE = process.env.RWALK_BASE || "http://127.0.0.1:8977";
const T = process.env.RWALK_TENANT || "brazosbend";
const EMAIL = process.env.RWALK_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.RWALK_PASSWORD || "S3cure!passw0rd";
/** `DSC-26-0002` on `A-11721` — the second cut this product ever completed. */
const CASE = process.env.RWALK_CASE || "DSC-26-0002";
const ACCT = process.env.RWALK_ACCT || "A-11721";
/** `DSC-26-0003` — Bramble Bakery, the blueprint's own worked account. */
const VISIT_CASE = process.env.RWALK_VISIT_CASE || "DSC-26-0003";
const VISIT_ACCT = process.env.RWALK_VISIT_ACCT || "A-11812";
const TODAY = process.env.RWALK_TODAY || "2026-09-20";
const CHROME = process.env.RWALK_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const SHOTS = process.env.RWALK_SHOTS || "/tmp/claude-0/dbld2-shots";
const DO_RECONNECT = process.env.RWALK_RECONNECT === "1";
const DO_VISIT = process.env.RWALK_VISIT === "1";
const DO_ARM = process.env.RWALK_ARM === "1";

console.log(`tree:   ${ROOT}`);
console.log(`app:    ${BASE}/${T}`);
console.log(`cases:  ${CASE} on ${ACCT} · ${VISIT_CASE} on ${VISIT_ACCT}`);
console.log(`writes: reconnect=${DO_RECONNECT} visit=${DO_VISIT} arm=${DO_ARM}\n`);

let pass = 0;
const failures = [];
const pageErrors = [];
const httpErrors = [];
const ok = (w) => { pass += 1; console.log(`  ✓ ${w}`); };
const bad = (w, saw) => { failures.push(`${w} — saw: ${saw}`); console.log(`  ✗ ${w}\n      saw: ${saw}`); };
const is = (c, w, saw) => (c ? ok(w) : bad(w, String(saw)));
const bodyText = (p) => p.evaluate(() => document.body.innerText.replace(/\s+/g, " "));

async function signIn(ctx, width) {
  const p = await ctx.newPage({ viewport: { width, height: 1800 } });
  p.setDefaultTimeout(25000);
  p.on("pageerror", (e) => pageErrors.push(`PAGEERROR ${e.message}`));
  p.on("response", async (r) => {
    if (r.url().includes("/api/") && r.status() >= 400) {
      httpErrors.push(
        `${r.status()} ${r.request().method()} ${r.url().replace(BASE, "")} ${(await r.text().catch(() => "")).slice(0, 220)}`,
      );
    }
  });
  await p.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
  await p.fill("#signin-email", EMAIL);
  await p.fill("#signin-password", PASSWORD);
  await Promise.all([
    p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
    p.click('button[type="submit"]'),
  ]);
  return p;
}

/** A POST through the page's own signed-in session — never a second client. */
async function post(page, url, body) {
  return page.evaluate(
    async ([u, b]) => {
      const r = await fetch(u, {
        method: "POST",
        headers: { "content-type": "application/json" },
        credentials: "include",
        body: JSON.stringify(b),
      });
      return { status: r.status, body: (await r.text()).slice(0, 400) };
    },
    [url, body],
  );
}

let browser;
try {
  browser = await chromium.launch({ executablePath: CHROME });
  const ctx = await browser.newContext();
  const page = await signIn(ctx, 1440);
  const api = `/api/${T}`;

  // ══════════════════════════════════════════════════════════════════════════
  // 1 · A CUT CASE OFFERS THE WAY BACK, AND NOT A CONTROL IT CAN NEVER USE
  // ══════════════════════════════════════════════════════════════════════════
  console.log(`═══ 1 · THE CASE RECORD · /disconnects/${CASE} ═══`);
  await page.goto(`${BASE}/${T}/disconnects/${CASE.toLowerCase()}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${SHOTS}/r1-cut-case.png`, fullPage: true });

  let text = await bodyText(page);
  is(/Cut/.test(text), "the case reads Cut", text.slice(0, 160));
  const reconnectBtn = await page.$('[data-testid="disconnect-record-reconnect"]');
  is(reconnectBtn !== null, "`Mark reconnecting` is on the record — the door that did not exist", "absent");
  is(
    (await page.$('[data-testid="disconnect-record-mark-cut"]')) === null,
    "`Mark as cut` is GONE rather than permanently greyed (law 2's mirror)",
    "still rendered",
  );
  is(
    (await page.$('[data-testid="disconnect-record-record-visit"]')) === null,
    "`Record visit` is not offered on a cut case (BR-CUS-1083)",
    "offered",
  );

  console.log("\n1a · THE REFUSAL IS VISIBLE TEXT, NOT A TOOLTIP (BR-SHL-025)");
  const refused = await page.$('[data-testid="disconnect-record-cut-refused"]');
  if (refused) {
    const words = (await refused.innerText()).trim();
    is(/owed/i.test(words), "the greyed commit carries the server's reason on screen", words);
    is(words.split(/\s+/).length <= 6, "…and it is six words or fewer (B14 rule 33)", words);
  } else {
    ok("nothing owed — the commit is live and needs no refusal");
  }
  is(
    !/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}/i.test(text),
    "no database id is the visible value of any field (B14 rule 31)",
    (text.match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}[^ ]*/i) ?? ["none"])[0],
  );

  console.log("\n1b · THE DIALOG — two money figures, each labelled for what it is");
  // ⚠ **THE HEADER BUTTON IS DISABLED WHILE THE ACCOUNT OWES, AND THAT IS THE
  // PRODUCT WORKING.** Clicking it anyway is how a walk reports a timeout as a
  // finding; the dialog is opened only when the commit is live.
  const commitLive = await page.isEnabled('[data-testid="disconnect-record-reconnect"]');
  if (commitLive) {
    await page.click('[data-testid="disconnect-record-reconnect"]');
    await page.waitForTimeout(1200);
    await page.screenshot({ path: `${SHOTS}/r2-reconnect-dialog.png`, fullPage: true });
    const money = await page.$('[data-testid="disconnect-reconnect-money"]');
    is(money !== null, "the dialog draws `To clear` beside `Owes now`", "no money panel");
    if (money) console.log(`      ${(await money.innerText()).replace(/\s+/g, " ")}`);
    await page.keyboard.press("Escape");
    await page.waitForTimeout(600);
  } else {
    ok("the commit is DISABLED while the account owes — BR-PAY-036, and the gate is live");
  }

  // ══════════════════════════════════════════════════════════════════════════
  // 2 · THE PAYMENT, THEN THE TWO STEPS BACK
  // ══════════════════════════════════════════════════════════════════════════
  if (DO_RECONNECT) {
    console.log("\n═══ 2 · THE WAY BACK, PRESSED ═══");
    // ⚠ **THE PAYMENT IS A REAL ONE THROUGH THE PAYMENTS DOOR.**
    // `mark_reconnecting` gates on AR, so a walk that mocked the balance would
    // be proving the screen against itself. The amount is read from the
    // account, never typed here.
    const owed = await page.evaluate(
      async ([u]) => {
        const r = await fetch(u, { credentials: "include" });
        const j = await r.json();
        return j?.to_clear?.arrears?.stored ?? null;
      },
      [`${api}/accounts/${await accountId(page, api, ACCT)}/reconnection-terms`],
    );
    console.log(`      arrears read from the product: ${owed}`);
    const acct = await accountId(page, api, ACCT);
    // ⚠ **`cleared_at` IS LOAD-BEARING AND THE FIRST RUN OF THIS WALK OMITTED
    // IT.** `record_payment` writes `processing` when no clearing date is
    // given, and a PROCESSING payment is excluded from AR — correctly, because
    // the money has not arrived. The walk reported "the payment posted" (201,
    // truthfully) and the gate went on refusing, which is law 7's *check that
    // passes wrongly*: the assertion was about the HTTP status and the thing
    // under test is the BALANCE.
    const paid = await post(page, `${api}/accounts/${acct}/payments`, {
      idempotency_key: `rwalk-${Date.now()}`,
      amount: owed,
      posted_at: TODAY,
      cleared_at: TODAY,
      method: "cash",
      memo: "Reconnection walk — settles the arrears so the gate can be pressed",
    });
    is(paid.status === 201 || paid.status === 200, `the payment of ${owed} posted`, JSON.stringify(paid));
    // ⚠ **ASSERT THE BALANCE, NOT THE STATUS CODE.**
    const after = await page.evaluate(
      async ([u]) => (await (await fetch(u, { credentials: "include" })).json())?.to_clear?.arrears?.stored ?? null,
      [`${api}/accounts/${acct}/reconnection-terms`],
    );
    is(after === "0.0000", "…and the account now owes nothing — the GATE's own figure", String(after));

    await page.reload({ waitUntil: "networkidle" });
    await page.waitForTimeout(1500);
    await page.click('[data-testid="disconnect-record-reconnect"]');
    await page.waitForTimeout(1200);
    await page.screenshot({ path: `${SHOTS}/r3-reconnect-ready.png`, fullPage: true });
    await page.click('button:has-text("Mark reconnecting")');
    await page.waitForTimeout(2500);
    await page.reload({ waitUntil: "networkidle" });
    await page.waitForTimeout(1500);
    text = await bodyText(page);
    is(/Reconnecting/.test(text), "the case now reads Reconnecting", text.slice(0, 160));
    const step = await page.getAttribute('[data-testid="disconnect-record-reconnect"]', "data-step");
    is(step === "restore_service", "the commit slot has moved to `Restore service`", String(step));
    await page.screenshot({ path: `${SHOTS}/r4-reconnecting.png`, fullPage: true });

    console.log("\n2a · RESTORE — and the status note the drawing never had");
    await page.click('[data-testid="disconnect-record-reconnect"]');
    await page.waitForTimeout(1200);
    const note = await page.$('[data-testid="disconnect-reconnect-no-status"]');
    if (note) console.log(`      status note: ${(await note.innerText()).replace(/\s+/g, " ")}`);
    await page.screenshot({ path: `${SHOTS}/r5-restore-dialog.png`, fullPage: true });
    await page.click('button:has-text("Restore service")');
    await page.waitForTimeout(2500);
    await page.reload({ waitUntil: "networkidle" });
    await page.waitForTimeout(1500);
    text = await bodyText(page);
    is(/Restored/.test(text), "the case reads Restored and has left the register", text.slice(0, 160));
    await page.screenshot({ path: `${SHOTS}/r6-restored.png`, fullPage: true });
  }

  // ══════════════════════════════════════════════════════════════════════════
  // 3 · A CREW ATTENDS AND DOES NOT CUT
  // ══════════════════════════════════════════════════════════════════════════
  if (DO_ARM) {
    console.log("\n═══ 3a · ARMING A CASE — through the five doors that have no screen ═══");
    const acct = await accountId(page, api, VISIT_ACCT);
    for (let i = 0; i < 3; i += 1) {
      await post(page, `${api}/accounts/${acct}/disconnect-case/advance`, {});
    }
    const notice = await post(page, `${api}/accounts/${acct}/disconnect-case/notices`, {
      tier: "tier_3_48_hour",
      on_date: "2026-09-10",
      channels: ["certified_mail"],
    });
    console.log(`      notice: ${notice.status} ${notice.body.slice(0, 100)}`);
    const notices = await page.evaluate(
      async ([u]) => (await (await fetch(u, { credentials: "include" })).json()),
      [`${api}/accounts/${acct}/disconnect-notices`],
    );
    const rows = notices?.notices ?? notices?.results ?? (Array.isArray(notices) ? notices : []);
    console.log(`      notices on file: ${rows.length}`);
    const tier3 = rows.filter((n) => n.tier === "tier_3_48_hour");
    for (const n of tier3) {
      const proof = await post(page, `${api}/disconnect-notices/${n.notice_id ?? n.id}/proof`, {
        channel: "certified_mail",
        served_on: "2026-09-12",
        reference: "RA 4821 9930 US",
        recorded_by: "S. Ortiz",
      });
      console.log(`      proof: ${proof.status} ${proof.body.slice(0, 90)}`);
      if (proof.status < 400) break;
    }
    const sched = await post(page, `${api}/disconnects/schedule`, {
      account_id: acct,
      cut_on: "2026-09-18",
      reason: "non_payment",
      services: { electric: "full_disconnection", water: "full_disconnection" },
    });
    console.log(`      schedule: ${sched.status} ${sched.body.slice(0, 120)}`);
  }

  console.log(`\n═══ 3 · THE FAILED VISIT · /disconnects/${VISIT_CASE} ═══`);
  await page.goto(`${BASE}/${T}/disconnects/${VISIT_CASE.toLowerCase()}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${SHOTS}/v1-scheduled.png`, fullPage: true });
  text = await bodyText(page);
  console.log(`      state on screen: ${(text.match(/CASE [A-Z0-9-]+ [^·]{0,60}/) ?? [""])[0]}`);
  const visitBtn = await page.$('[data-testid="disconnect-record-record-visit"]');
  is(visitBtn !== null, "`Record visit` is on a scheduled case — the door that did not exist", "absent");

  if (visitBtn) {
    await visitBtn.click();
    await page.waitForTimeout(1200);
    await page.screenshot({ path: `${SHOTS}/v2-visit-dialog.png`, fullPage: true });
    // ⚠ **SCOPED TO THE DIALOG.** `[data-outcome]` also matches the
    // protections table behind it, so an unscoped selector reported four
    // protection rows as outcomes — a walk finding that was the walk's.
    const outcomes = await page.$$eval("label[data-outcome]", (els) =>
      els.map((e) => `${e.getAttribute("data-outcome")} → ${e.querySelector("[data-move]")?.getAttribute("data-move") ?? "?"}`),
    );
    is(outcomes.length === 4, "four outcomes are offered, each with where it sends the case", outcomes.join(" | "));
    console.log(`      ${outcomes.join("\n      ")}`);
    const followUp = await page.$('[data-testid="disconnect-visit-no-follow-up"]');
    is(followUp !== null, "…and the screen says nobody is sent back out", "absent");

    if (DO_VISIT) {
      await page.click('label[data-outcome="locked_gate"]');
      await page.fill("#disconnect-visit-note", "Padlock on the meter box; nobody on site.");
      // ⚠ **THE HEADER BUTTON AND THE DIALOG'S COMMIT CARRY THE SAME WORDS**,
      // so a bare text selector resolves to two and picks the one behind the
      // overlay. Scoped to the modal.
      await page.click('.modal-overlay button:has-text("Record visit")');
      await page.waitForTimeout(2500);
      await page.reload({ waitUntil: "networkidle" });
      await page.waitForTimeout(1500);
      text = await bodyText(page);
      is(/At notice/.test(text), "the case has MOVED to At notice", text.slice(0, 200));
      is(!/Cut date 0?9\/18/.test(text), "…and the cut date is gone from the head", text.slice(0, 220));
      await page.screenshot({ path: `${SHOTS}/v3-after-visit.png`, fullPage: true });
    }
  }

  // ══════════════════════════════════════════════════════════════════════════
  // 4 · AT 1280, THE STAFF MINIMUM
  // ══════════════════════════════════════════════════════════════════════════
  console.log("\n═══ 4 · 1280, THE LAPTOP MINIMUM ═══");
  const narrow = await signIn(ctx, 1280);
  await narrow.goto(`${BASE}/${T}/disconnects/${CASE.toLowerCase()}`, { waitUntil: "networkidle" });
  await narrow.waitForTimeout(1200);
  const sideways = await narrow.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 2);
  is(!sideways, "the record does not scroll sideways at 1280", String(sideways));
  await narrow.screenshot({ path: `${SHOTS}/r7-1280.png`, fullPage: true });
} finally {
  if (browser) await browser.close();
}

async function accountId(page, api, accountNo) {
  return page.evaluate(
    async ([u, no]) => {
      const r = await fetch(`${u}/accounts?f.q=${encodeURIComponent(no)}&page_size=5`, {
        credentials: "include",
      });
      const j = await r.json();
      const rows = j?.results ?? j?.items ?? [];
      return (rows.find((a) => a.account_no === no) ?? rows[0])?.id ?? null;
    },
    [api, accountNo],
  );
}

console.log(`\n${"═".repeat(74)}`);
console.log(`${pass} passed · ${failures.length} failed`);
for (const f of failures) console.log(`  ✗ ${f}`);
if (pageErrors.length) console.log(`\nPAGE ERRORS:\n  ${pageErrors.join("\n  ")}`);
if (httpErrors.length) console.log(`\nHTTP ≥400:\n  ${httpErrors.join("\n  ")}`);
process.exit(failures.length + pageErrors.length ? 1 : 0);
