// ── Trace ────────────────────────────────────────────────────────────────────
// Change:   CR-125-BRC07 — THE DISCONNECT CASE RECORD, blueprint p143 with its
//           two dialogs on p144 and p145. PO ruling, verbatim: *"okay build it
//           as per specification and as per what you ahve mentioned -
//           Disconnect details view — every section - i will consolidate
//           actions - too many actions - keep critical ones"*.
// Rules:    B14 rule 31 (the record is addressed by CASE NUMBER) · rule 33 ·
//           rule 40 (the page-head title is 32px) · BR-SHL-025 (a refused
//           control renders disabled WITH ITS REASON) · CLAUDE.md hard-won
//           laws 2, 6, 7
// ─────────────────────────────────────────────────────────────────────────────
//
// ⚠ **THIS IS THE ONLY CHECK IN THE REPOSITORY THAT READS RENDERED OUTPUT, AND
// IT IS A PERSON WITH A BROWSER.** Hard-won law 6: *"diff the running app
// against the prototype — nine defects were found this way and by nothing
// else."* Every assertion below is one a unit test cannot make, because a unit
// test mounts a component and this drives the shipped bundle through a real
// router, a real query client and a real API.
//
// ⚠ **`ROOT` IS DERIVED FROM THIS FILE'S OWN PATH** (`DEF-CUS-6028`): a walk
// that hard-codes `/home/user/SMARTBillHub` drives YOUR bundle and then reads
// the SHARED checkout's Django, which is on somebody else's branch, and nothing
// says so.
//
// ⚠ **IT WRITES NOTHING.** `Hold the case` and `Mark as cut` are both opened
// and neither is submitted: this record's two writes are real acts against a
// real household's case, and a walkthrough that holds a case leaves a
// protection row behind on a tenant other lanes are reading.
//
//   node 10-scripts/cr125_disconnect_record_walk.mjs
//   DRW_BASE=http://127.0.0.1:8997 DRW_CASE=DSC-26-0003 node …
//
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..");
const require = createRequire(path.join(ROOT, "07-frontend/package.json"));
const { chromium } = require("playwright");

const BASE = process.env.DRW_BASE || "http://127.0.0.1:8997";
const T = process.env.DRW_TENANT || "brazosbend";
const EMAIL = process.env.DRW_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.DRW_PASSWORD || "S3cure!passw0rd";
const CASE = process.env.DRW_CASE || "DSC-26-0003";
const CHROME = process.env.DRW_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const SHOTS = process.env.DRW_SHOTS || "/tmp/disconnect-record-walk";

let pass = 0;
const failures = [];
const pageErrors = [];
function ok(what) { pass += 1; console.log(`  ✓ ${what}`); }
function bad(what, saw) { failures.push(`${what} — saw: ${saw}`); console.log(`  ✗ ${what}\n      saw: ${saw}`); }
function is(cond, what, saw) { cond ? ok(what) : bad(what, saw); }

async function signIn(ctx, width) {
  const p = await ctx.newPage({ viewport: { width, height: 1600 } });
  p.setDefaultTimeout(25000);
  p.on("pageerror", (e) => pageErrors.push(`PAGEERROR ${e.message}`));
  await p.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
  await p.fill("#signin-email", EMAIL);
  await p.fill("#signin-password", PASSWORD);
  await Promise.all([
    p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
    p.click('button[type="submit"]'),
  ]);
  return p;
}

let browser;
try {
  browser = await chromium.launch({ executablePath: CHROME });
  const ctx = await browser.newContext();
  const page = await signIn(ctx, 1440);

  // ═══ 1 · THE ADDRESS IS THE CASE NUMBER ════════════════════════════════════
  console.log("\n1 · THE RECORD OPENS AT ITS OWN ADDRESS — the CASE NUMBER, never a uuid");
  await page.goto(`${BASE}/${T}/disconnects/${CASE.toLowerCase()}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${SHOTS}/p143-1440.png`, fullPage: true });

  const text = await page.evaluate(() => document.body.innerText.replace(/\s+/g, " "));
  is(!/Case not found/i.test(text), "the lowercase URL from the blueprint resolves", text.slice(0, 160));
  is(text.includes(CASE), `the kicker carries ${CASE}`, text.slice(0, 200));

  // ═══ 2 · rule 40 — THE PAGE-HEAD TITLE IS 32px ═════════════════════════════
  console.log("\n2 · THE HEAD — B14 rule 40, and the four drawn chips");
  const head = await page.evaluate(() => {
    const h = document.querySelector("h1");
    return h === null ? null : {
      text: h.textContent.trim(),
      size: getComputedStyle(h).fontSize,
    };
  });
  is(head !== null && head.size === "32px", "the title is 32px (rule 40)", JSON.stringify(head));
  is(head !== null && head.text.length > 0 && !/^[0-9a-f-]{36}$/i.test(head.text),
     "the title is the customer and never an id (rule 31)", JSON.stringify(head));
  const addr = await page.$eval('[data-testid="disconnect-record-address"]',
    (n) => n.textContent.trim()).catch(() => null);
  is(addr !== null && addr.length > 10, "the address is drawn, walked to the premises", String(addr));

  // ═══ 3 · THE FIVE SECTIONS ═════════════════════════════════════════════════
  console.log("\n3 · p143's SECTIONS — every one on the page");
  for (const [sel, what] of [
    ['[data-testid="disconnect-record-case"]', "THE CASE"],
    ['[data-testid="disconnect-record-protections"]', "PROTECTIONS CHECKED"],
    ['[data-testid="disconnect-record-cut"]', "WHAT A CUT WOULD DO"],
    ['[data-testid="disconnect-record-not-a-closeout"]', "the red banner"],
  ]) {
    const n = await page.$(sel);
    is(n !== null, `${what} is rendered`, sel);
  }
  const notices = await page.$('[data-testid="disconnect-record-notices"]');
  const noNotices = await page.$('[data-testid="disconnect-record-no-notices"]');
  is(notices !== null || noNotices !== null, "NOTICES SENT is rendered (table or its empty state)", "neither");

  // ═══ 4 · WHAT THE PRODUCT DOES NOT HOLD, IT SAYS ═══════════════════════════
  console.log("\n4 · THE TWO FACTS WITH NO SOURCE — stated, never faked, never a dash");
  is(/Oldest debt/.test(text) && /Not counted/.test(text),
     "`Oldest debt` is drawn and reads `Not counted`", text.match(/Oldest debt[^A-Z]{0,40}/)?.[0] ?? "absent");
  is(/Raised by/.test(text) && /Name not kept/.test(text),
     "`Raised by` is drawn and reads `Name not kept`", text.match(/Raised by[^A-Z]{0,40}/)?.[0] ?? "absent");
  is(/Opened on/.test(text), "the DATE half IS drawn beside it", "absent");

  console.log("\n   …and the rationale is NOT on the page (B14 rule 33)");
  is(!/nothing in this repository/i.test(text),
     "the server's `detail` never reaches the page body", "a rationale sentence is visible");

  console.log("\n   …and no delivery claim is made on any notice");
  for (const word of ["Queued", "certified sent"]) {
    is(!new RegExp(`\\b${word}\\b`, "i").test(text.replace("Queued is not sent", "")),
       `no notice row claims \`${word}\``, "a delivery state is drawn");
  }

  console.log("\n   …and no reconnection price is invented");
  const feeRow = await page.evaluate(() => {
    const dts = [...document.querySelectorAll("dt")];
    const dt = dts.find((d) => /Reconnection fee/i.test(d.textContent));
    return dt === undefined ? null : dt.parentElement.textContent.replace(/\s+/g, " ").trim();
  });
  is(feeRow !== null && !/\d/.test(feeRow.replace(/Reconnection fee/i, "")),
     "the reconnection fee carries a sentence and no figure", String(feeRow));

  // ═══ 5 · THE THREE ACTIONS, AND NO FOURTH ══════════════════════════════════
  console.log("\n5 · THE ACTION SET — three, which is the PO's ruling");
  const buttons = await page.evaluate(() => {
    const root = document.querySelector("header, .page-head") ?? document.body;
    return [...root.querySelectorAll("button, a")]
      .map((b) => b.textContent.replace(/\s+/g, " ").trim())
      .filter((t) => t.length > 0 && t.length < 40);
  });
  for (const drawn of ["Hold the case", "Open the account", "Mark as cut"]) {
    is(buttons.some((b) => b === drawn), `\`${drawn}\` is on the page`, buttons.join(" | ").slice(0, 200));
  }
  for (const undrawn of ["Stop the ladder", "Advance", "Lift", "Mark reconnecting", "Restore service"]) {
    is(!buttons.some((b) => b.includes(undrawn)), `\`${undrawn}\` is NOT on the page`, buttons.join(" | ").slice(0, 200));
  }

  // ═══ 6 · `Mark as cut` IS GREYED, WITH ITS REASON WHERE A PERSON READS IT ══
  console.log("\n6 · THE GREYED BUTTON — and the reason a clerk can actually read");
  const cut = await page.evaluate(() => {
    const b = document.querySelector('[data-testid="disconnect-record-mark-cut"]');
    const r = document.querySelector('[data-testid="disconnect-record-cut-refused"]');
    return {
      disabled: b === null ? null : b.disabled,
      describedBy: b === null ? null : b.getAttribute("aria-describedby"),
      // ⚠ **THE COMPUTED VISIBILITY, NOT MERELY THE NODE.** A refusal in the
      // DOM behind `display:none` reads as present to a selector and as
      // nothing at all to a clerk — law 7's *looking at the wrong thing*.
      reasonText: r === null ? null : r.textContent.trim(),
      reasonVisible: r === null ? false : r.offsetParent !== null || getComputedStyle(r).display !== "none",
      reasonInATitle: r === null ? null : r.getAttribute("title"),
    };
  });
  is(cut.disabled === true, "`Mark as cut` is disabled, as p143 draws it", JSON.stringify(cut));
  is(cut.reasonText !== null && cut.reasonText.length > 0 && cut.reasonVisible,
     "its reason is VISIBLE TEXT on the page (BR-SHL-025)", JSON.stringify(cut));
  is(cut.reasonInATitle === null, "the reason is NOT hidden in a `title`", JSON.stringify(cut));
  is(cut.describedBy !== null, "the button points at it for a screen reader", JSON.stringify(cut));

  // ═══ 7 · p144 — THE HOLD DIALOG OPENS AND PROMISES ONLY WHAT IS TRUE ═══════
  console.log("\n7 · p144 — the Hold dialog, and the two promises it no longer makes");
  await page.click('[data-testid="disconnect-record-hold"]');
  await page.waitForTimeout(900);
  await page.screenshot({ path: `${SHOTS}/p144-hold-1440.png`, fullPage: true });
  const dialog = await page.evaluate(() => {
    const effects = document.querySelector('[data-testid="disconnect-hold-effects"]');
    const dispute = document.querySelector('[data-testid="disconnect-hold-dispute"]');
    return {
      effects: effects === null ? null : effects.innerText.replace(/\s+/g, " ").trim(),
      dispute: dispute === null ? null : dispute.innerText.replace(/\s+/g, " ").trim(),
      disputeDisabled: dispute === null ? null : dispute.querySelector("input")?.disabled ?? null,
      reviewOn: document.querySelector("#disconnect-hold-review-on") !== null,
    };
  });
  is(dialog.effects !== null && /ladder stops/i.test(dialog.effects),
     "it promises the ladder stops — the one that is TRUE", String(dialog.effects));
  is(dialog.effects !== null && /cut date stays/i.test(dialog.effects),
     "it states the cut date STAYS, which is the fact a clerk needs", String(dialog.effects));
  is(dialog.effects !== null && !/cleared/i.test(dialog.effects) && !/On hold/i.test(dialog.effects),
     "it no longer promises a cleared date or an `On hold` state", String(dialog.effects));
  is(dialog.disputeDisabled === true, "the drawn fourth reason is refused, not offered", String(dialog.dispute));
  is(dialog.dispute !== null && /cannot be recorded/i.test(dialog.dispute),
     "…and its reason is VISIBLE TEXT beside it", String(dialog.dispute));
  is(dialog.reviewOn === true, "`Review on` is offered for a medical certificate", JSON.stringify(dialog));

  console.log("\n   …and it disappears for a payment plan (BR-CUS-043)");
  await page.click('input[name="disconnect-hold-kind"][value="payment_plan"]');
  await page.waitForTimeout(500);
  const afterPlan = await page.evaluate(() => ({
    reviewOn: document.querySelector("#disconnect-hold-review-on") !== null,
    said: document.querySelector('[data-testid="disconnect-hold-no-review-date"]')?.textContent.trim() ?? null,
  }));
  is(afterPlan.reviewOn === false && afterPlan.said !== null,
     "`Review on` is gone and the screen says why", JSON.stringify(afterPlan));

  // ⚠ NOTHING IS SUBMITTED — see the header.
  await page.keyboard.press("Escape");
  await page.waitForTimeout(600);

  // ═══ 8 · 1280, THE LAPTOP MINIMUM ══════════════════════════════════════════
  console.log("\n8 · 1280 — the staff app's laptop minimum (PO ruling 2026-09-10)");
  const narrow = await signIn(await browser.newContext(), 1280);
  await narrow.goto(`${BASE}/${T}/disconnects/${CASE.toLowerCase()}`, { waitUntil: "networkidle" });
  await narrow.waitForTimeout(1200);
  await narrow.screenshot({ path: `${SHOTS}/p143-1280.png`, fullPage: true });
  const overflow = await narrow.evaluate(() =>
    document.documentElement.scrollWidth - document.documentElement.clientWidth);
  is(overflow <= 0, "the page does not scroll sideways at 1280", `${overflow}px of overflow`);

  // ═══ 9 · THE DOOR OUT ══════════════════════════════════════════════════════
  console.log("\n9 · `Open the account` actually opens the account");
  await page.click('[data-testid="disconnect-record-open-account"]');
  await page.waitForTimeout(2000);
  const landed = page.url();
  is(landed.includes(`/${T}/accounts/`) && !landed.includes("//accounts"),
     "it lands on an account under this tenant", landed);

  console.log(`\n${pass} passed · ${failures.length} failed`);
  if (pageErrors.length > 0) console.log("PAGE ERRORS:\n  " + pageErrors.join("\n  "));
  for (const f of failures) console.log("FAIL " + f);
  console.log(`screenshots: ${SHOTS}`);
  process.exitCode = failures.length === 0 ? 0 : 1;
} finally {
  if (browser !== undefined) await browser.close();
}
