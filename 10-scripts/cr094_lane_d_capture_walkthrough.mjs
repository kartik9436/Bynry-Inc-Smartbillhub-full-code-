// ── Trace ──────────────────────────────────────────────
// Change:   CR-094-BRC01 capture wave, lane D — the six steps of the New
//           request wizard rebuilt from the accounts blueprint's page IMAGES
//           (p076–p081, B14 rule 42).
// Rules:    B14 rule 41 (the product matches the blueprint) · rule 31 (no
//           database id is a visible value) · rule 32/33 (nothing internal on
//           screen; the copy caps) · rule 40 (the 32px page title) ·
//           BR-CUS-092 as amended 2026-09-15 · BR-CUS-1022 · BR-CUS-1070 ·
//           hard rule 8 (an address lives on `premises`)
// Tests:    07-frontend/src/features/customers/ServiceRequestCapturePage.test.tsx
// ───────────────────────────────────────────────────────
//
// **THIS IS THE ONLY CHECK IN THE REPOSITORY THAT READS RENDERED OUTPUT**
// (hard-won law 6). It signs in, opens each of the six steps at 1440 and at
// 1280, drives the controls the rulings of 2026-09-15 added, and shoots every
// state — so the next change to this screen re-runs the walk instead of
// re-remembering it.
//
// RUN IT (from `07-frontend`, which is where `playwright-core` is installed):
//
//     WEB=http://127.0.0.1:8112 \
//     CHROMIUM=/opt/pw-browsers/chromium-1194/chrome-linux/chrome \
//     OUT=/tmp/lane-D-shots \
//     node ../10-scripts/cr094_lane_d_capture_walkthrough.mjs
//
// ⚠ **TWO WAYS IT LIES, BOTH MET WHILE IT WAS BEING WRITTEN, BOTH WORTH
// KNOWING BEFORE YOU BELIEVE A RED:**
//   * **A STALE SERVER.** `runserver --noreload` holds the code it booted
//     with. The premises picker answered `404` for three runs and the walk
//     reported *the register said nothing* — a real-looking product defect
//     over a backend started before the route landed. The walk now prints the
//     ROW COUNT beside the verdict so a zero is distinguishable from a silence.
//   * **A CASE-SENSITIVE LABEL.** `Field` uppercases its label in CSS and
//     `innerText` returns the RENDERED text, so comparing against the
//     catalogue string failed over three rows that were on the screen. A check
//     that fails wrongly costs as much as one that passes wrongly.
//
// The console-error tally counts the sandbox's own noise — a blocked
// `fonts.googleapis.com` fetch and the in-flight requests this walk aborts by
// navigating — so read the named lines, not the total.
// Lane D · CR-094-BRC01 — walk all six capture steps at 1440 and 1280 against
// the accounts blueprint p076–p081, and shoot each one.
//
// Hard-won law 6: no gate in this repo reads rendered output. This is it.
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";

// ⚠ **ESM RESOLVES FROM THE SCRIPT, NOT FROM THE CWD**, so a bare
// `import "playwright-core"` fails from `10-scripts/` however you invoke it.
// This is `12-smoke-walkthrough.mjs`'s own idiom, borrowed rather than
// re-invented: the package is already pinned in `07-frontend` for the e2e
// suite and this script carries no dependency of its own.
const requireFrontend = createRequire(
  new URL("../07-frontend/package.json", import.meta.url),
);
const { chromium } = requireFrontend("playwright-core");

const WEB = process.env.WEB ?? "http://127.0.0.1:8112";
const TENANT = "brazosbend";
const EMAIL = "dana@brazosbendutilities.com";
const PASSWORD = "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/lane-D-shots";
mkdirSync(OUT, { recursive: true });

const problems = [];
const note = (m) => { console.log(m); };
const fail = (m) => { problems.push(m); console.log("  ✗ " + m); };
const ok = (m) => console.log("  ✓ " + m);

const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM ?? undefined,
});

async function walk(width, height, tag) {
  const ctx = await browser.newContext({ viewport: { width, height } });
  const page = await ctx.newPage();
  const consoleErrors = [];
  page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text()); });
  page.on("requestfailed", (r) => consoleErrors.push(`REQUEST FAILED ${r.url()} — ${r.failure()?.errorText}`));

  note(`\n═══ ${width}×${height} ═══`);

  // ── sign in ──
  await page.goto(`${WEB}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(`**/${TENANT}/dashboard`, { timeout: 25000 });
  note("signed in");

  for (const step of [1, 2, 3, 4, 5, 6]) {
    await page.goto(`${WEB}/${TENANT}/requests/new?step=${step}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(900);
    const shot = `${OUT}/${tag}-step${step}.png`;
    await page.screenshot({ path: shot, fullPage: true });
    note(`step ${step} → ${shot}`);

    const body = await page.locator("body").innerText();

    // The head, on every step (B14 rule 40 · the drawn kicker/title/sub-line).
    const h1 = await page.locator("h1").first().innerText().catch(() => "");
    if (!h1.trim()) fail(`step ${step}: no <h1>`);
    if (!body.includes(`Step ${step} of 6`)) fail(`step ${step}: sub-line missing`);

    // Nothing internal reaches a clerk (B14 rules 31/32).
    const leak = body.match(/\b(?:BR|DEF|OQ|CR|GT|US|EP|ADR)-[A-Z]{0,3}-?\d{3,5}\b/);
    if (leak) fail(`step ${step}: internal id on screen — ${leak[0]}`);
    const uuid = body.match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i);
    if (uuid) fail(`step ${step}: a database id is visible — ${uuid[0]}`);

    // No sideways scroll on the page body.
    const over = await page.evaluate(() =>
      document.documentElement.scrollWidth - document.documentElement.clientWidth);
    if (over > 2) fail(`step ${step}: body scrolls sideways by ${over}px`);

    if (step === 1) {
      for (const want of ["Applying as", "How did this reach us?", "Full name",
                          "Date of birth", "Driver's licence", "Social Security Number"]) {
        body.includes(want) ? ok(`step 1 draws ${want}`) : fail(`step 1 missing ${want}`);
      }
      if (body.includes("not recorded on a request yet")) {
        fail("step 1 still states the date-of-birth absence over a live input");
      }
      // switch to a business and prove the person's evidence is not offered
      await page.locator('label:has(input[name="applicant_kind"][value="business"])').click();
      await page.waitForTimeout(400);
      const asBiz = await page.locator("body").innerText();
      asBiz.includes("Tax ID") ? ok("a business is asked for its Tax ID") : fail("no Tax ID for a business");
      if (asBiz.includes("Driver's licence")) fail("a business is offered a driving licence");
      if (asBiz.includes("Date of birth")) fail("a business is offered a date of birth");
      await page.screenshot({ path: `${OUT}/${tag}-step1-business.png`, fullPage: true });
      note(`step 1 (business) → ${OUT}/${tag}-step1-business.png`);
    }

    if (step === 2) {
      // ⚠ **A DROPDOWN, AND THE TAG IS WHAT THIS ASSERTS** — PO, of the built
      // step 2: *"please note on step 2 it is drop down for Category and sub
      // category"*. A presence check alone passed over the segmented row this
      // replaced, so it would pass over a regression back to it.
      const cat = page.locator("#account_type_code");
      (await cat.count()) && (await cat.evaluate((e) => e.tagName)) === "SELECT"
        ? ok("Category is a dropdown") : fail("Category is not a <select>");
      const sub = page.locator("#account_subtype_id");
      (await sub.count()) && (await sub.evaluate((e) => e.tagName)) === "SELECT"
        ? ok("Sub-category is a dropdown") : fail("Sub-category is not a <select>");
      // …and they sit on ONE row, as p076 draws them.
      const sameRow = await page.evaluate(() => {
        const a = document.querySelector("#account_type_code")?.closest(".field");
        const b = document.querySelector("#account_subtype_id")?.closest(".field");
        return a && b ? a.parentElement === b.parentElement : false;
      });
      sameRow ? ok("the two dropdowns share one row") : fail("the two dropdowns are not side by side");
      // The dropdown opens UNANSWERED — the gate depends on it.
      (await cat.inputValue()) === ""
        ? ok("Category opens unanswered") : fail("Category opens pre-answered");
      body.includes("Which services does this property need?")
        ? ok("step 2 draws the services question") : fail("step 2 missing the services question");
      const m = body.match(/(\d+) of (\d+) selected/);
      m ? ok(`the drawn count reads "${m[0]}"`) : fail("no 'N of M selected' line");
      const cards = await page.locator('[data-service-card]').count().catch(() => 0);
      cards === 0 ? ok("no service CARDS — the multiselect replaced them") : fail(`${cards} service cards still drawn`);
      // pick two and see the per-service table appear
      const add = page.locator('[data-chip-add="capture-services"]');
      if (await add.count()) {
        const opts = await add.locator("option").allTextContents();
        const pick = opts.filter((o) => !o.startsWith("Add a service")).slice(0, 2);
        for (const label of pick) { await add.selectOption({ label }); await page.waitForTimeout(250); }
        await page.waitForTimeout(500);
        const after = await page.locator("body").innerText();
        after.includes("When each one is wanted")
          ? ok("the per-service table appears once services are picked")
          : fail("no per-service start table after picking");
        const rows = await page.locator("[data-service-row]").count();
        rows === pick.length ? ok(`${rows} row(s), one per picked service`) : fail(`${rows} rows for ${pick.length} services`);
        const m2 = after.match(/(\d+) of (\d+) selected/);
        if (m2 && Number(m2[1]) !== pick.length) fail(`count says ${m2[1]} after picking ${pick.length}`);
        else if (m2) ok(`count moved to "${m2[0]}"`);
        await page.screenshot({ path: `${OUT}/${tag}-step2-picked.png`, fullPage: true });
        note(`step 2 (picked) → ${OUT}/${tag}-step2-picked.png`);
      } else fail("no add-a-service control found");
    }

    if (step === 3) {
      body.includes("Street address or premise")
        ? ok("step 3 draws the drawn street label") : fail("step 3 missing 'Street address or premise'");
      if (body.includes("Plot or parcel")) fail("the plot control is still on step 3");
      else ok("the plot is off step 3");
      if (body.includes("How many units")) fail("the unit-count question is still asked");
      const box = page.locator("#address_as_given");
      // ⚠ two characters MINIMUM — the server ignores a shorter `q` rather
      // than refusing it (BR-SHL-011), and so does the screen's `enabled`.
      await box.fill("Willow Bend");
      await page.waitForTimeout(1200);
      const res = page.locator("[data-premises-option]");
      const n = await res.count();
      note(`  (picker answered ${n} row(s) for "Willow Bend")`);
      if (n > 0) {
        const label = await res.first().innerText();
        ok(`the register answered with ${n} row(s), first "${label.trim()}"`);
        if (/[0-9a-f]{8}-[0-9a-f]{4}/i.test(label)) fail("a premises option shows a uuid");
        await res.first().click();
        await page.waitForTimeout(900);
        const picked = await page.locator("body").innerText();
        picked.includes("From the premises record")
          ? ok("the premises' own facts show read-only") : fail("no walked premises facts after picking");
        picked.includes("What the register matched")
          ? ok("the match-evidence table is drawn") : fail("no match-evidence table after picking");
        await page.screenshot({ path: `${OUT}/${tag}-step3-picked.png`, fullPage: true });
        note(`step 3 (picked) → ${OUT}/${tag}-step3-picked.png`);
      } else {
        const b2 = await page.locator("body").innerText();
        b2.includes("No premises match.") ? ok("the register answered 'no match' and offers + Premises")
          : fail("the register search returned nothing and said nothing");
      }
    }

    if (step === 4) {
      for (const chip of ["All", "Required", "Missing", "Rejected"]) {
        (await page.getByRole("button", { name: chip, exact: true }).count())
          ? ok(`chip ${chip} is drawn`) : fail(`chip ${chip} missing`);
      }
      const before = await page.locator('input[type="checkbox"]').count();
      await page.locator('[data-doc-filter="required"]').click();
      await page.waitForTimeout(400);
      const after = await page.locator('input[type="checkbox"]').count();
      after < before ? ok(`Required narrowed ${before} → ${after}`)
        : fail(`Required did not narrow (${before} → ${after})`);
      await page.screenshot({ path: `${OUT}/${tag}-step4-required.png`, fullPage: true });
      note(`step 4 (Required) → ${OUT}/${tag}-step4-required.png`);
    }

    if (step === 5) {
      if (body.includes("Nothing here is recorded, and nothing here is in the books"))
        fail("step 5 still prints the superseded 'posts nothing' sentence");
      else ok("the superseded 'posts nothing' sentence is gone");
      body.includes("No invoice and no account yet.")
        ? ok("the surviving half is printed") : fail("the surviving half is missing");
      const now = page.locator('label:has(input[name="fee_timing"][value="collect_now"])');
      if (await now.count()) {
        await now.first().click();
        await page.waitForTimeout(400);
        const sel = page.locator("#fee_method");
        await sel.selectOption("card");
        await page.waitForTimeout(400);
        const card = await page.locator("body").innerText();
        card.includes("Last four digits") ? ok("card asks for the last four") : fail("no card last-four field");
        card.includes("Authorisation code") ? ok("card asks for the auth code") : fail("no auth code field");
        if (/card number|expiry|security code|CVV/i.test(card)) fail("a full card field is drawn");
        if (card.includes("Cheque number")) fail("cheque fields drawn beside the card fields");
        await page.screenshot({ path: `${OUT}/${tag}-step5-card.png`, fullPage: true });
        note(`step 5 (card) → ${OUT}/${tag}-step5-card.png`);
        await sel.selectOption("cheque");
        await page.waitForTimeout(400);
        const chq = await page.locator("body").innerText();
        chq.includes("Cheque number") && chq.includes("Bank")
          ? ok("cheque asks for number and bank") : fail("cheque fields missing");
        if (chq.includes("Last four digits")) fail("card fields still drawn on a cheque");
        await page.screenshot({ path: `${OUT}/${tag}-step5-cheque.png`, fullPage: true });
        note(`step 5 (cheque) → ${OUT}/${tag}-step5-cheque.png`);
      } else fail("no fee-timing control on step 5");
    }

    if (step === 6) {
      const right = page.locator('[data-review-column="right"]');
      (await right.count()) ? ok("step 6 has a right-hand column") : fail("step 6 has no right column");
      const rt = (await right.count()) ? await right.innerText() : "";
      for (const want of ["Documents", "Fees", "On submit"]) {
        rt.includes(want) ? ok(`the right column holds ${want}`) : fail(`the right column is missing ${want}`);
      }
      // ⚠ **CASE-INSENSITIVE, BECAUSE `Field` UPPERCASES ITS LABEL IN CSS.**
      // `innerText` returns the RENDERED text, so a literal comparison against
      // the catalogue string fails over a row that is on the screen — a check
      // that fails wrongly is as bad as one that passes wrongly (law 7).
      const rtl = rt.toLowerCase();
      for (const row of ["Request number", "State", "Waiting on"]) {
        rtl.includes(row.toLowerCase()) ? ok(`On submit draws ${row}`) : fail(`On submit missing ${row}`);
      }
      if (rt.includes("What goes out to the applicant"))
        fail("the held messaging block was built");
      else ok("the held messaging block is absent, as briefed");
      const cols = await page.evaluate(() => {
        const g = document.querySelector('[data-review-column="left"]')?.parentElement;
        return g ? getComputedStyle(g).gridTemplateColumns : null;
      });
      note(`  (review grid columns: ${cols})`);
    }
  }

  // ⚠ **THE SANDBOX'S OWN NOISE IS NAMED AND COUNTED, NOT FAILED — AND
  // COUNTING IT IS THE POINT.** Two kinds arrive here and neither is the
  // product: the container's proxy has no CA for `fonts.googleapis.com`, and
  // this walk aborts its own in-flight `/api/.../me`-style reads every time it
  // navigates to the next step. Failing on them would train a reader to
  // ignore this whole section, which is how a true red acquires the
  // protective colouring of a known one (law 7). **A declared blind spot with
  // no NUMBER attached is indistinguishable from an empty one**, so the count
  // is printed beside what was checked.
  const noise = (e) =>
    /fonts\.googleapis\.com|ERR_CERT_AUTHORITY_INVALID/.test(e) ||
    (/ERR_ABORTED/.test(e) && /\/api\//.test(e));
  const real = consoleErrors.filter((e) => !noise(e));
  const ignored = consoleErrors.length - real.length;
  if (real.length) {
    for (const e of real.slice(0, 5)) fail(`console error: ${e.slice(0, 160)}`);
  } else {
    ok(`no console errors the product caused (${ignored} sandbox line(s) ignored: blocked webfont, aborted in-flight reads)`);
  }

  await ctx.close();
}

await walk(1440, 1000, "w1440");
await walk(1280, 900, "w1280");
await browser.close();

console.log("\n══════════════════════════════════════════");
if (problems.length === 0) console.log("WALK CLEAN — every drawn element found at both widths");
else { console.log(`WALK FOUND ${problems.length} PROBLEM(S):`); for (const p of problems) console.log(" · " + p); }
process.exit(problems.length === 0 ? 0 : 1);
