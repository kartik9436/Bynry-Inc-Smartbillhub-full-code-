// ── STEP 2 OF THE PROPERTY SALE: CAN A CLERK TYPE A BRAND-NEW BUYER? ─────────
//
// ── Trace ────────────────────────────────────────────────────────────────────
// Defect:  `DEF-CUS-6549` — step 2 showed a search box, a *Search customer*
//          button and *"Search for the buyer first."* and nothing else. PO,
//          verbatim, 2026-09-24: *"you need to take all buyer detaisl the way
//          were taking- full name, email, phone, ids etc, document, cateory sub
//          category - all - then allow provide a button to search for customer
//          id; what you did is you removed all buyer details and only provide
//          search - this is wrong"*.
// Ruling:  PO 2026-09-24, option (a) — *"the clerk has the buyer in front of
//          them, and a wrong phone caught at the counter is cheaper than one
//          caught by a returned bill. - thissi correct - please correct this"*.
//          The FORM is the primary path; SEARCH is a convenience beside it; a
//          hit FILLS the form and leaves it EDITABLE.
// Rules:   `BR-CUS-1081` (the buyer carries what an account needs) ·
//          `BR-CUS-1023` (one identifier, one implementation) · B14 rules 21,
//          31, 32, 33, 43 · CLAUDE.md hard-won laws 2, 6, 7
// Screens: `TRF-02` (S89) step 2
// ─────────────────────────────────────────────────────────────────────────────
//
// ⚠ **IT RUNS IN THE TREE IT IS IN** (`DEF-CUS-6028`): `ROOT` comes from
// `import.meta.url`, never a typed path, so a worktree drives ITS OWN bundle.
//
// ⚠ **IT WRITES NOTHING.** No sale is committed, no customer is minted; the
// walk reaches step 3 and stops. The one search it runs is a GET.
//
// ⚠ **EVERY CHECK BELOW WAS SHOWN RED ON THE BROKEN BUILD BEFORE IT WAS
// TRUSTED GREEN** (hard-won law 7). The one that is easiest to get wrong:
//   * **A FIELD IS ASKED FOR BY ITS OWN CONTROL ID, NEVER BY BODY TEXT.** The
//     word "Email" appears in the page chrome and in the finder's own result
//     card, so `body.includes("Email")` is true on a step with no form on it.
//     Every field is asked as `#trf_buyer_<name>` and its VALUE is read back.
//
//   TBW_BASE    default http://127.0.0.1:4482 — the SPA join (`server.mjs` over
//               a `vite build`). The vite DEV server has no `/api` proxy.
//   TBW_TENANT  default brazosbend
//   TBW_SHOTS   default the scratchpad's transfer-buyer folder
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..");
const require = createRequire(path.join(ROOT, "07-frontend/package.json"));
const { chromium } = require("playwright");

const BASE = process.env.TBW_BASE || "http://127.0.0.1:4482";
const T = process.env.TBW_TENANT || "brazosbend";
const EMAIL = process.env.TBW_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.TBW_PASSWORD || "S3cure!passw0rd";
const ACC = process.env.TBW_ACCOUNT || "AC-2026-00012";
const CHROME = process.env.TBW_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const SHOTS =
  process.env.TBW_SHOTS ||
  "/tmp/claude-0/-home-user-SMARTBillHub/6ba8cd67-91ed-5ae1-ac39-8519d4343c20/scratchpad/transfer-buyer";
mkdirSync(SHOTS, { recursive: true });

let pass = 0, fail = 0;
const failures = [];
function ok(what, cond, detail = "") {
  if (cond) { pass += 1; console.log(`  ✓ ${what}`); }
  else { fail += 1; failures.push(`${what}${detail ? ` — ${detail}` : ""}`); console.log(`  ✗ ${what}${detail ? ` — ${detail}` : ""}`); }
  return cond;
}
const saw = (w) => console.log(`  · ${w}`);

/** Every scrollable box on the page back to the top, THEN the shot. */
async function shoot(p, path) {
  await p.evaluate(() => {
    window.scrollTo(0, 0);
    for (const el of Array.from(document.querySelectorAll("*"))) {
      if (el.scrollTop > 0) el.scrollTop = 0;
    }
  });
  await p.waitForTimeout(300);
  await p.screenshot({ path, fullPage: true });
}

/** A tick in this kit is an `sr-only` input behind its label. */
const pressTick = (p, id) => p.click(`label[for=${id}]`);

async function signIn(p) {
  await p.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
  await p.fill("#signin-email", EMAIL);
  await p.fill("#signin-password", PASSWORD);
  await Promise.all([
    p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
    p.click('button[type="submit"]'),
  ]);
}

/** Step 1 → step 2, through the account search the step actually has. */
async function toStepTwo(p) {
  await p.goto(`${BASE}/${T}/transfers/new`, { waitUntil: "networkidle" });
  await p.fill("#trf_account", ACC);
  await p.waitForTimeout(1200);
  const option = await p.$(`[role="option"]:has-text("${ACC}")`);
  if (option !== null) { await option.click(); await p.waitForTimeout(600); }
  await p.click('[data-wizard="actions"] button:has-text("Continue")');
  await p.waitForTimeout(1200);
}

/** The value of one control, or `null` when the control is not on the page.
 *  ⚠ The distinction matters: an EMPTY field and an ABSENT field are different
 *  facts, and this whole defect is the second one wearing the first's clothes. */
async function fieldValue(p, id) {
  const el = await p.$(`#${id}`);
  if (el === null) return null;
  return (await el.inputValue()).trim();
}
async function present(p, id) { return (await p.$(`#${id}`)) !== null; }

/** The fields the step draws whatever else is true — asked by control id,
 *  never by label, because the finder's own result card draws the words
 *  "Email" and "Phone" too. */
const ALWAYS = [
  ["trf_buyer_name", "Full name"],
  ["trf_buyer_applicant_email", "Email"],
  ["trf_buyer_applicant_phone", "Phone"],
  ["trf_buyer_add_co_applicant", "Add a co-applicant"],
  ["trf_buyer_mailing_same", "Same as service address"],
];

/** ⚠ **THESE APPEAR WITH THE STATED KIND AND THAT IS `BR-CUS-1022`, NOT A
 *  DEFECT** — *"asking for both and leaving one blank turns a rule into a
 *  habit"*. An unstated kind is asked for no identifier at all. */
const PER_KIND = [
  ["trf_buyer_date_of_birth", "Date of birth"],
  ["trf_buyer_ssn", "SSN"],
  ["trf_buyer_drivers_licence", "Driving licence"],
];

(async () => {
  const browser = await chromium.launch({ executablePath: CHROME, args: ["--no-sandbox"] });
  //: ⚠ **1440 WIDE IS THE DESIGN TARGET AND THE HEIGHT IS DELIBERATELY TALL.**
  //: The app scrolls an INNER container, not the document, so Playwright's
  //: `fullPage` captures from wherever that container happens to be sitting —
  //: the first run of this file handed over a picture of the middle of the
  //: form with no stepper in it. A viewport the whole step fits inside is the
  //: only thing that makes the shot say what it claims to say.
  const page = await browser.newPage({ viewport: { width: 1440, height: 2200 } });
  try {
    await signIn(page);
    console.log("\n── STEP 2 AS THE CLERK FIRST SEES IT ────────────────────────");
    await toStepTwo(page);
    await shoot(page, `${SHOTS}/step-2-the-buyer.png`);
    saw(`screenshot → ${SHOTS}/step-2-the-buyer.png`);

    const finder = await page.$('[data-customer-finder]');
    ok("the customer search is on the step", finder !== null);

    for (const [id, label] of ALWAYS) {
      ok(`${label} is on the step before any search`, await present(page, id), `#${id} is absent`);
    }
    ok(
      "Person or company is on the step before any search",
      (await page.$("[id^='trf_buyer_kind']")) !== null,
    );
    ok(
      "the buyer's Documents panel is on the step before any search",
      (await page.$("[data-step-content='buyer-documents']")) !== null,
    );

    const refusal = await page.$('[data-buyer-shortfall]');
    const refusalText = refusal === null ? "" : (await refusal.textContent()).trim();
    ok(
      'the step does not refuse with "Search for the buyer first."',
      !/search for the buyer first/i.test(refusalText),
      `it says ${JSON.stringify(refusalText)}`,
    );

    console.log("\n── A BRAND-NEW BUYER, NEVER SEARCHED FOR, REACHES STEP 3 ────");
    const kindOption = await page.$('label.seg-opt:has-text("Person")');
    if (kindOption !== null) await kindOption.click();
    await page.waitForTimeout(400);
    for (const [id, label] of PER_KIND) {
      ok(`${label} appears once the kind is stated`, await present(page, id), `#${id} is absent`);
    }
    await page.fill("#trf_buyer_name", "Tim Aiden");
    await page.fill("#trf_buyer_applicant_phone", "512-555-0143");
    await page.fill("#trf_buyer_applicant_email", "tim.aiden@example.com");
    if (await present(page, "trf_buyer_date_of_birth")) {
      await page.fill("#trf_buyer_date_of_birth", "1984-03-11");
    }
    await page.waitForTimeout(400);
    const stillRefusing = await page.$('[data-buyer-shortfall]');
    ok(
      "a filled-in buyer earns no refusal",
      stillRefusing === null,
      stillRefusing === null ? "" : (await stillRefusing.textContent()).trim(),
    );
    await page.click('[data-wizard="actions"] button:has-text("Continue")');
    await page.waitForTimeout(1200);
    const onThree = (await page.$("#trf_sold_on")) !== null;
    ok("a clerk who never searched reaches step 3 (the date of sale)", onThree);

    console.log("\n── A SEARCH HIT FILLS THE FORM AND LEAVES IT EDITABLE ───────");
    await page.click('[data-wizard="actions"] button:has-text("Back")');
    await page.waitForTimeout(900);
    await page.fill("#trf_buyer_customer_q", "Castillo");
    await page.click('[data-customer-search]');
    await page.waitForTimeout(1800);
    const rows = await page.$$('[data-customer-row], [data-customer-card="match"]');
    saw(`the search answered with ${rows.length} card/row(s)`);
    const linkButton = await page.$('[data-customer-card="match"] button, [data-customer-row] button');
    if (linkButton !== null) {
      await linkButton.click();
      await page.waitForTimeout(900);
      const filledName = await fieldValue(page, "trf_buyer_name");
      ok("the linked customer's name FILLED the form's own field", filledName !== null && filledName !== "", `name reads ${JSON.stringify(filledName)}`);
      const nameEl = await page.$("#trf_buyer_name");
      const disabled = nameEl === null ? true : await nameEl.isDisabled();
      ok("the filled field is still EDITABLE", !disabled);
      const phoneBefore = await fieldValue(page, "trf_buyer_applicant_phone");
      await page.fill("#trf_buyer_applicant_phone", "512-555-0199");
      await page.waitForTimeout(300);
      const phoneAfter = await fieldValue(page, "trf_buyer_applicant_phone");
      ok(
        "a stale phone can be corrected after the hit",
        phoneAfter === "512-555-0199" && phoneAfter !== phoneBefore,
        `was ${JSON.stringify(phoneBefore)}, now ${JSON.stringify(phoneAfter)}`,
      );
      // ⚠ **THE IDENTIFIER BOXES ARE WITHDRAWN ON A HIT, AND THAT IS NOT A
      // LOCK — IT IS THE ONE FIELD THE DOOR WOULD DROP.** `transferPlanOf`
      // sends a linked buyer as `customer_id` with `identity: {}`, so an SSN
      // typed here reaches no column at all (`DEF-CUS-6487`'s shape), and
      // `BR-CUS-1020` refuses a second place a government identifier is typed.
      // Everything else stays live, which is the whole of the PO's ruling.
      ok(
        "no identifier box is offered for a customer the server already holds one for",
        !(await present(page, "trf_buyer_ssn")),
      );
      ok("the co-applicant block survives the hit", await present(page, "trf_buyer_add_co_applicant"));
      ok("the mailing-address block survives the hit", await present(page, "trf_buyer_mailing_same"));
      await shoot(page, `${SHOTS}/step-2-after-search.png`);
      saw(`screenshot → ${SHOTS}/step-2-after-search.png`);
    } else {
      ok("the search returned a linkable customer", false, "no Link button was drawn — seed a matching customer");
      await shoot(page, `${SHOTS}/step-2-after-search.png`);
    }
  } catch (e) {
    fail += 1;
    failures.push(`the walk died — ${e.message}`);
    console.log(`  ✗ the walk died — ${e.message}`);
    try { await page.screenshot({ path: `${SHOTS}/died.png`, fullPage: true }); } catch { /* nothing */ }
  } finally {
    await browser.close();
  }
  console.log(`\n${pass} passed, ${fail} failed`);
  for (const f of failures) console.log(`  ✗ ${f}`);
  process.exit(fail === 0 ? 0 : 1);
})();
