// ── Trace ────────────────────────────────────────────────────
// Defects: `DEF-CUS-5934` (the PO: *"step 4 when last tick is press - uI
//          breaks"*) · `DEF-CUS-5948` (every exit landed on *"This account
//          could not be opened"*) · `DEF-CUS-5949` (step 5 told nobody, over a
//          sentence that said no channel existed)
// Screens: S89 / `TRF-02`, all five steps (Accounts blueprint p124–p133)
// Rules:   B14 rule 32 (one sentence a section, no internal code in clerk copy)
//          · rule 33 (label ≤3 words · fact ≤6 · instruction ≤6 a sentence ·
//          rationale ZERO words on screen) · hard-won law 2 and its mirror
//          (never draw a control that sends nothing) · hard-won law 6 (diff the
//          running app — no gate here reads rendered output) · law 7 (a check
//          must be shown RED on the thing it is written for)
// ─────────────────────────────────────────────────────
//
// ⚠⚠ **THE TRANSFER WIZARD HAD NO WALKTHROUGH AND THAT IS WHY THE PRODUCT
// OWNER IS THE ONE WHO FOUND ALL OF THIS.** Move-in, move-out and the clerk
// request walk each have a script; this flow had none, its own suites are green
// at 39 passed / 2 todo, `tsc` is clean, and the conformance lane that mapped
// the whole surface the same day states in its own report that it did not boot
// a stack. Every assertion below is read off a RENDERED PAGE or off a real
// navigation, never off a constant.
//
// ⚠ **IT PRESSES CONTROLS. That is the whole point of the file.** The existing
// suite renders step 4 with `renderToStaticMarkup` and therefore cannot press
// the one control that step has. This walk presses every enabled control on
// every step, each from a fresh session, and fails on a React error boundary.
//
// ⚠ **IT HAS A BEFORE MODE (`WALK_EXPECT_OK=0`), so the before is reproducible
// rather than remembered.** Against a build from before this change it expects:
// `Its relationships` / `The premise` / the payment-plan paragraph / `A bill
// records what was sent` on step 1, the false `A move-out usually needs a final
// read` and the `What happens on save` table on step 2, `Who gets told this
// figure` on step 4, `No channel exists yet` on step 5, and `Save & exit`
// landing on **Accounts · Failed · This account could not be opened**.
//
// ⚠ **IT WRITES NOTHING.** It stops before `Complete the sale ✓`; the only
// requests it issues are GETs plus whatever the park panel is asked for, and it
// never opens that panel's submit. Counts on the tenant are unchanged by a run.
//
// ⚠ **THE SERVED BUNDLE IS THE ONE THAT COUNTS.** Build first; nothing on the
// page says how old the bundle is.
//
// ⚠ **BEFORE MODE IS NOT MEANT TO COME OUT ALL GREEN, AND A READER WHO EXPECTS
// THAT WILL MISREAD IT.** Measured on the unfixed build: **39 passed · 5 failed**.
// The 39 are the copy assertions, whose polarity `moved()` flips — each one
// confirming the old sentence really was on the screen. The 5 are the control
// sweep, which is NOT flipped and must never be: a control that lands a clerk on
// a failure screen is a defect on whichever build you are looking at, and on the
// unfixed build `Save & exit` and `← Transfers` do exactly that on all five
// steps. So before mode reproduces the OLD COPY and still reports the OLD BREAK.
// On the fixed build the whole file is **44 passed · 0 failed**.
//
//   WALK_BASE       the SPA join (default http://127.0.0.1:8973)
//   WALK_TENANT     default brazosbend
//   WALK_ACCOUNT    the account id step 1 resolves to
//   WALK_EMAIL / WALK_PASSWORD
//   WALK_EXPECT_OK  1 expects the fixed copy, 0 expects the OLD behaviour
//   WALK_SHOT       screenshot directory, optional
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.WALK_BASE || "http://127.0.0.1:8973";
const T = process.env.WALK_TENANT || "brazosbend";
const ACC = process.env.WALK_ACCOUNT || "01a0aff9-6869-7f40-b42e-a969b03fe2c5";
const EMAIL = process.env.WALK_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.WALK_PASSWORD || "S3cure!passw0rd";
const EXPECT_OK = (process.env.WALK_EXPECT_OK || "1") === "1";
const SHOT = process.env.WALK_SHOT || "";
const CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

const KILL = setTimeout(() => {
  console.error("REFUSED: walk exceeded 10 minutes");
  process.exit(3);
}, 600000);

let pass = 0, fail = 0;
const ok = (what, cond, detail = "") => {
  if (cond) { pass++; console.log(`  ✓ ${what}`); }
  else { fail++; console.log(`  ✗ ${what}${detail ? ` — ${detail}` : ""}`); }
};
/** An assertion whose POLARITY is what this change moved. In before mode the
 *  expectation flips, so one file proves both sides. */
const moved = (what, nowTrue) => ok(what, EXPECT_OK ? nowTrue : !nowTrue,
  EXPECT_OK ? "still there / still missing on this build" : "this build already carries the fix");

// The step-1 copy the Product Owner ruled off, quoted from the live screen.
const STEP1_GONE = [
  "SMARTBillHub cannot yet show whether anything hangs off this account",
  "Who owns or manages this address",
  "Nothing here has checked whether this account has a payment plan",
  "A bill records what was sent",
];
const STEP2_GONE = [
  "A move-out usually needs a final read",
  "What happens on save",
  "This flow does not wait for the visit",
  "No meter reading is taken",
];
// ⚠ **THE FIFTH DELETION CANNOT BE SEEN ON A TENANT THAT HAS TEMPLATES, AND A
// SILENT PASS OVER IT WOULD BE LAW 7's *reporting zero over a scope it
// excludes*.** *"This utility has published no field-work templates for this
// moment yet"* only renders when the offer comes back EMPTY. On `brazosbend`
// it never does, so the walk says which branch it was able to reach instead of
// claiming the sentence is gone.
const STEP2_TEMPLATES_GONE = "published no field-work templates";

let browser;
try {
  browser = await chromium.launch({ executablePath: CHROME });

  /** A fresh signed-in page. Every press below gets one, so a press that
   *  navigates cannot change the answer for the press after it. */
  async function session() {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
    const page = await ctx.newPage();
    page.setDefaultTimeout(25000);
    const errs = [];
    page.on("pageerror", (e) => errs.push(`PAGEERROR ${e.message}`));
    page.on("console", (m) => {
      if (m.type() === "error" && !m.text().includes("ERR_CERT")) errs.push(`CONSOLE ${m.text().slice(0, 200)}`);
    });
    await page.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
    await page.fill("#signin-email", EMAIL);
    await page.fill("#signin-password", PASSWORD);
    await Promise.all([
      page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
      page.click('button[type="submit"]'),
    ]);
    return { ctx, page, errs };
  }

  /** Walk to `step`, filling only what the step before it refuses without. */
  async function walkTo(page, step) {
    await page.goto(`${BASE}/${T}/transfers/new`, { waitUntil: "networkidle" });
    await page.waitForSelector('[data-account-finder=""] input');
    await (await page.$('[data-account-finder=""] input')).fill(ACC);
    await page.waitForTimeout(2000);
    if (step === 1) return;
    await page.click('button:has-text("Continue")');
    await page.waitForSelector("#trf_buyer_name");
    if (step === 2) return;
    // BR-CUS-1023 — the step refuses on the buyer, so a kind and one identifier.
    await page.$$eval("input[type=radio]", (ns) => ns.find((n) => n.value === "person").click());
    await page.waitForTimeout(250);
    await page.fill("#trf_buyer_name", "Walk, Rosa");
    await page.fill("#trf_buyer_ssn", "123-45-6789");
    await page.click('button:has-text("Continue")');
    await page.waitForSelector("#trf_sold_on, input[type=date]");
    if (step === 3) return;
    await page.fill((await page.$("#trf_sold_on")) ? "#trf_sold_on" : "input[type=date]", "2026-10-01");
    await page.click('button:has-text("Continue")');
    await page.waitForSelector("#trf_shown_to_buyer");
    if (step === 4) return;
    await page.click('button:has-text("Continue")');
    await page.waitForTimeout(1200);
  }

  /**
   * ⚠ **WHAT COUNTS AS *the screen broke*, AND THE FIRST VERSION GOT IT WRONG
   * IN BOTH DIRECTIONS.**
   *
   * It missed the real one: pressing `Save & exit` on the unfixed build lands
   * on **"Accounts · Failed · This account could not be opened"**, which is a
   * rendered failure SCREEN and not a React boundary, so the regex walked past
   * it and only a stray console 404 gave it away.
   *
   * And it raised a false one: it treated ANY console error as a crash, so
   * `Complete the sale ✓` answering **409 `A-10432 is not linked to a customer`**
   * failed the sweep — over a refusal the screen renders correctly, in the
   * server's own words, which is `BR-SHL-020` working. A handled 4xx is the
   * product doing its job; an uncaught exception is not.
   */
  const CRASHED = /Unexpected Application Error|Something went wrong|This account could not be opened|We could not find that/i;
  const boundary = (text) => CRASHED.test(text);
  /** A console line worth failing on. `Failed to load resource` is an HTTP
   *  status the screen may well be showing the clerk; an uncaught error is not. */
  const realError = (line) => !/Failed to load resource/i.test(line);

  /** ⚠ **THE FIRST VERSION OF THIS SELECTOR READ `[data-wizard="content"]`
   *  ALONE AND REPORTED "1 control pressed" ON STEP 4** — it saw the tick and
   *  none of `Back`, `Continue`, `Save & exit`, `Park` or the step rail, all of
   *  which live in the frame around the content. A sweep that silently excludes
   *  the footer is law 7's *reporting zero over a scope it excludes*, and on
   *  step 4 the footer is where the two broken controls actually were. It is
   *  the whole screen now, minus the shell's own navigation, and the count is
   *  printed so a reader can see what it covered. */
  const WIZARD_CONTROLS =
    'main button, main label[for], main a[href]';

  console.log(`\n═══ transfer wizard · ${BASE}/${T} · expecting ${EXPECT_OK ? "the FIXED" : "the OLD"} build ═══`);

  // ── STEP 1 ────────────────────────────────────────────────────────────────
  {
    const { ctx, page, errs } = await session();
    await walkTo(page, 1);
    const body = await page.innerText("body");
    if (SHOT) await page.screenshot({ path: `${SHOT}/step1.png`, fullPage: true });
    console.log("\nstep 1 · the account being sold");
    for (const phrase of STEP1_GONE) {
      moved(`gone: "${phrase.slice(0, 46)}…"`, !body.includes(phrase));
    }
    // The two the PO kept, because both are facts a clerk needs.
    ok("kept: the Stays with you badge", body.includes("Stays with you"));
    ok("kept: What this sale will not touch", body.includes("What this sale will not touch"));
    // B14 rule 33 — an instruction caps at six words a sentence.
    const hint = await page.$eval('[data-account-finder=""]', (n) => {
      const p = n.querySelector("p, [data-note]");
      return p ? p.innerText.trim() : "";
    }).catch(() => "");
    const words = hint.split(/\s+/).filter(Boolean).length;
    console.log(`    the search hint reads ${JSON.stringify(hint)} — ${words} words`);
    moved(`the search hint is six words or fewer (rule 33)`, words > 0 && words <= 6);
    ok("no error boundary on step 1", !boundary(body), errs.join(" | "));
    await ctx.close();
  }

  // ── STEP 2 ────────────────────────────────────────────────────────────────
  {
    const { ctx, page, errs } = await session();
    await walkTo(page, 2);
    const body = await page.innerText("body");
    if (SHOT) await page.screenshot({ path: `${SHOT}/step2.png`, fullPage: true });
    console.log("\nstep 2 · the buyer");
    for (const phrase of STEP2_GONE) {
      moved(`gone: "${phrase.slice(0, 46)}…"`, !body.includes(phrase));
    }
    // The tick list itself is CR-070 wave P and stays — only the furniture went.
    // The empty-templates sentence, honestly scoped.
    const offered = await page.$$eval("[data-field-work-template]", (ns) => ns.length);
    const emptyBranch = (await page.$("[data-field-work-empty]")) !== null;
    if (offered > 0) {
      console.log(`    ⓘ NOT EXERCISED on this tenant: "${STEP2_TEMPLATES_GONE}" renders only when the`);
      console.log(`      offer is EMPTY, and this tenant offers ${offered} template(s). Run with a tenant`);
      console.log(`      that has published none to check it, or trust the prop and not this walk.`);
    } else {
      moved(`gone: "${STEP2_TEMPLATES_GONE}"`, !emptyBranch && !body.includes(STEP2_TEMPLATES_GONE));
    }
    ok("kept: the field-visit tick list is still offered",
       (await page.$("[data-raise-field-work]")) !== null);
    ok("kept: the buyer block still asks for a name", (await page.$("#trf_buyer_name")) !== null);
    ok("no error boundary on step 2", !boundary(body), errs.join(" | "));
    await ctx.close();
  }

  // ── STEP 3 ────────────────────────────────────────────────────────────────
  {
    const { ctx, page, errs } = await session();
    await walkTo(page, 3);
    const body = await page.innerText("body");
    if (SHOT) await page.screenshot({ path: `${SHOT}/step3.png`, fullPage: true });
    console.log("\nstep 3 · the date of sale");
    const one = async (sel, label) => {
      const text = await page.$eval(sel, (n) => n.innerText.trim()).catch(() => "");
      const sentences = text.split(/(?<=\.)\s+/).filter((x) => x.trim() !== "").length;
      console.log(`    ${label}: ${JSON.stringify(text)} — ${sentences} sentence(s)`);
      moved(`${label} is one line`, text !== "" && sentences === 1);
    };
    await one("[data-date-does]", "what the date does");
    await one("[data-date-not]", "what it does not do");
    // The PO kept this one by name: it stops a clerk promising a split bill.
    ok("kept: Nothing is prorated at a sale. One period, one bill.",
       body.includes("Nothing is prorated at a sale. One period, one bill."));
    // The four money rows were to be deleted and the PO reversed it — "we need
    // all" — so their ABSENCE is now the defect.
    for (const row of ["Base charge", "Billing cycle", "Current period", "Next bill"]) {
      ok(`kept: the ${row} row`, body.includes(row));
    }
    ok("no error boundary on step 3", !boundary(body), errs.join(" | "));
    await ctx.close();
  }

  // ── STEP 4 — `DEF-CUS-5934`, AND THE PRESS IS THE ASSERTION ───────────────
  {
    const { ctx, page, errs } = await session();
    await walkTo(page, 4);
    const before = await page.innerText("body");
    if (SHOT) await page.screenshot({ path: `${SHOT}/step4-before.png`, fullPage: true });
    console.log("\nstep 4 · what they take on");
    moved(`gone: the "Who gets told this figure" panel`, !before.includes("Who gets told this figure"));
    ok("kept: the money the buyer takes on", before.includes("Account balance") && before.includes("Deposit on file"));

    // ⚠ THE DEFECT ITSELF. The suite renders this step statically; only a press
    // can answer it.
    const boxBefore = await page.$eval("#trf_shown_to_buyer", (n) => n.checked);
    await page.click('label[for="trf_shown_to_buyer"]');
    await page.waitForTimeout(1000);
    const after = await page.innerText("body");
    const boxAfter = await page.$eval("#trf_shown_to_buyer", (n) => n.checked).catch(() => null);
    if (SHOT) await page.screenshot({ path: `${SHOT}/step4-after.png`, fullPage: true });
    ok("DEF-CUS-5934 — the last tick records itself", boxBefore === false && boxAfter === true,
       `before ${boxBefore}, after ${boxAfter}`);
    ok("DEF-CUS-5934 — the step survives the press", after.includes("What the buyer takes on") && !boundary(after));
    ok("DEF-CUS-5934 — no uncaught error on the press", errs.length === 0, errs.join(" | "));

    // And forward, because a tick that records and then blocks is the same
    // defect one step later.
    await page.click('button:has-text("Continue")');
    await page.waitForTimeout(1200);
    const five = await page.innerText("body");
    ok("DEF-CUS-5934 — Continue still reaches step 5", five.includes("One account, one new owner") && !boundary(five));
    await ctx.close();
  }

  // ── STEP 5 — `DEF-CUS-5949` ───────────────────────────────────────────────
  {
    const { ctx, page, errs } = await session();
    await walkTo(page, 5);
    const body = await page.innerText("body");
    if (SHOT) await page.screenshot({ path: `${SHOT}/step5.png`, fullPage: true });
    console.log("\nstep 5 · review");
    moved(`gone: the false "No channel exists yet"`, !body.includes("No channel exists yet"));
    moved(`says plainly that nobody is told`, body.includes("Nobody is told about this sale."));
    // Hard-won law 2's mirror: nothing on this panel may look like a send.
    ok("no send control is drawn over a queue that has never delivered",
       (await page.$('[data-send] input, [data-send] button')) === null);
    ok("kept: the owner record still wants updating by hand",
       body.includes("The property's owner record still wants updating by hand."));
    ok("kept: what this will do", body.includes("What this will do"));
    ok("no error boundary on step 5", !boundary(body), errs.join(" | "));
    await ctx.close();
  }

  // ── THE EXITS — `DEF-CUS-5948`. ASSERT THE PAGE, NEVER THE href ───────────
  {
    console.log("\nthe way out of the wizard");
    for (const [label, press] of [
      ["Save & exit", async (page) => page.click('button:has-text("Save & exit")')],
      ["the ← Transfers head link", async (page) => page.click('a:has-text("Transfers")')],
    ]) {
      const { ctx, page } = await session();
      await walkTo(page, 4);
      await press(page);
      await page.waitForTimeout(1500);
      const landed = await page.innerText("body");
      const url = page.url();
      console.log(`    ${label} → ${url.replace(BASE, "")}`);
      moved(`${label} does not land on "This account could not be opened"`,
            !landed.includes("This account could not be opened"));
      moved(`${label} lands on the Transfers tab`, landed.includes("Transfers") && landed.includes("Move-ins"));
      await ctx.close();
    }
  }

  // ── EVERY ENABLED CONTROL ON EVERY STEP, ONE FRESH SESSION EACH ───────────
  {
    console.log("\nevery enabled control on the wizard, pressed once");
    for (const step of [1, 2, 3, 4, 5]) {
      const probe = await session();
      await walkTo(probe.page, step);
      const controls = await probe.page.$$eval(
        WIZARD_CONTROLS,
        (ns) => ns.map((n, i) => ({ i, text: (n.innerText || n.id || "").trim().slice(0, 34), disabled: n.disabled === true })),
      );
      await probe.ctx.close();
      let crashed = 0, skipped = [];
      for (const c of controls) {
        if (c.disabled) continue;
        // ⛔ **THE COMMIT IS NOT PRESSED, AND THAT IS THIS FILE'S OWN PROMISE.**
        // The header says the walk writes nothing; `Complete the sale ✓` is the
        // one control that would reassign a real account on a real tenant. A
        // sweep that presses *every* control would have quietly broken that
        // guarantee — hard-won law 1, a comment claiming a guarantee is not the
        // guarantee. It is named here so the skip is visible in the output
        // rather than silent.
        if (/Complete the sale/i.test(c.text)) { skipped.push(c.text); continue; }
        const { ctx, page, errs } = await session();
        await walkTo(page, step);
        await page.$$eval(
          WIZARD_CONTROLS,
          (ns, idx) => ns[idx]?.click(), c.i,
        ).catch(() => undefined);
        await page.waitForTimeout(900);
        const text = await page.innerText("body").catch(() => "");
        const hard = errs.filter(realError);
        if (boundary(text) || hard.length > 0) {
          crashed++;
          console.log(`    ✗ step ${step} · "${c.text}" → ${boundary(text) ? "LANDS ON A FAILURE SCREEN" : hard.join(" | ")}`);
        }
        await ctx.close();
      }
      const pressed = controls.filter((c) => !c.disabled && !/Complete the sale/i.test(c.text));
      console.log(`    step ${step} covered: ${pressed.map((c) => JSON.stringify(c.text)).join(", ")}`);
      if (skipped.length > 0) console.log(`    step ${step} NOT pressed, deliberately: ${skipped.join(", ")} — it writes`);
      ok(`step ${step}: ${pressed.length} controls pressed, none broke the screen`,
         crashed === 0 && pressed.length >= 4, pressed.length < 4 ? "the sweep saw too few controls — check the selector" : "");
    }
  }

  console.log(`\n═══ ${pass} passed · ${fail} failed ═══`);
} catch (error) {
  console.error("\nWALK FAILED:", error);
  fail++;
} finally {
  if (browser) await browser.close();
  clearTimeout(KILL);
}
process.exit(fail === 0 ? 0 : 1);
