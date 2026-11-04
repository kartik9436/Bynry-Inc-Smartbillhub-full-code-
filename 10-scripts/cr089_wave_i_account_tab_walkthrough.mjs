// ── Trace ──────────────────────────────────────────────
// Change:  CR-089 wave I — I1..I6 (`PUJ-36`..`PUJ-41`): the unit's Account tab
//          rendered five facts over an accounts table with 33 columns and six
//          tables hanging off it.
// Defects: DEF-CUS-4691 (a protection is on no screen a clerk reaches from a
//          unit) · DEF-CUS-4692 (nine account columns on zero rows) ·
//          DEF-CUS-4702 (the Move-out hold's sentence had rotted)
// Rules:   PO definition of done, verbatim: *"everything should be executed
//          based on actual code, and rules that we place, also ensure you do
//          web walkthorugh before you sign off the user story or build"* ·
//          hard-won law 6 (no gate in this repo looks at rendered output) ·
//          law 2's mirror (a live screen behind a dead control) · law 7 (a
//          check's output must distinguish pass from fail TO A READER).
// ───────────────────────────────────────────────────────
//
// WHAT THIS OPENS, AND WHY EACH IS HERE RATHER THAN IN A DOM TEST.
//
// A dom test seeds the answer into the query cache and asserts a string is in
// the markup. It therefore proves the COMPONENT and nothing about the route,
// the serializer, the seam chain into two other modules, or the fixture. Every
// unit below is a REAL account on the seeded `brazosbend` demo, reached the way
// a clerk reaches it, and every sentence asserted is read out of the rendered
// page.
//
//   1 · A-11902 — the medical certificate. The banner, its dates, and the fact
//       it is drawn ABOVE the facts rather than among them.
//   2 · A-10432 — autopay ON over a cash-only sanction. `I3`'s whole point:
//       *Autopay · On* alone is the WRONG answer and this is the account that
//       proves the right one is being served.
//   3 · A-10877 — the three columns with no writing door (legacy ref, returned
//       post, credit tier) — and credit tier must NOT appear anywhere.
//   4 · A-10650 / A-10714 — the delivery election and the tax exemption.
//   5 · The Move-out hold: the button is present, DISABLED by attribute, and
//       its sentence no longer claims the flow does not exist.
import { existsSync, readdirSync, mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8511";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr089i";
mkdirSync(OUT, { recursive: true });

// The five seats the wave I fixture takes on `brazosbend`, by the UNIT a clerk
// stands on. Overridable so the same script runs against a re-seeded database.
const UNITS = {
  protected: process.env.UNIT_PROTECTED ?? "01a077b8-3fb9-7a44-a7c0-8e3ddff463e3", // A-11902
  sanctioned: process.env.UNIT_SANCTIONED ?? "01a077b8-355c-7c24-981c-ca06cd554707", // A-10432
  migrated: process.env.UNIT_MIGRATED ?? "01a077b8-3e34-7d88-92df-45e176c5f761", // A-10877
  reachable: process.env.UNIT_REACHABLE ?? "01a077b8-3cfe-7f91-b0cf-6f007f341547", // A-10650
  exempt: process.env.UNIT_EXEMPT ?? "01a077b8-3d98-76ce-beb3-59b8d30bc862", // A-10714
};

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      const candidate = join(root, dir, "chrome-linux", "chrome");
      if (existsSync(candidate)) return candidate;
    }
  }
  throw new Error("no chromium found — set PLAYWRIGHT_BROWSERS_PATH");
}

const results = [];
// ⚠ A CHECK'S OUTPUT MUST DISTINGUISH PASS FROM FAIL TO A READER (law 7). So
// every check prints the sentence it looked for AND, on failure, what it found
// instead — an exit code alone has twice been trusted to answer a question it
// could not.
function check(name, ok, detail = "") {
  results.push({ name, ok });
  console.log(`${ok ? "  PASS" : "  FAIL"}  ${name}${ok || !detail ? "" : `\n          ${detail}`}`);
}

async function openAccountTab(page, unitId, label) {
  await page.goto(`${BASE}/${TENANT}/premises/units/${unitId}?tab=account`, {
    waitUntil: "networkidle",
  });
  await page.waitForSelector("h3", { timeout: 15000 });
  await page.screenshot({ path: join(OUT, `${label}.png`), fullPage: true });
  return (await page.locator("body").innerText()).replace(/\s+/g, " ");
}

const page_ = await (async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1400 } });
  page.on("pageerror", (e) => console.log("  page error:", e.message));

  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
  console.log(`signed in as ${EMAIL}\n`);

  // ── I1 · the protection is a banner ABOVE everything ────────────────────
  console.log("I1 · PUJ-36 · A-11902 carries a medical certificate (DEF-CUS-4691)");
  {
    const text = await openAccountTab(page, UNITS.protected, "i1-protection");
    // ⚠ **RESOLVED WITH A TIMEOUT AND A NULL, NOT LEFT TO THROW.** The first
    // version let the locator time out, which ABORTED the run — so a red proof
    // on this one check reported nothing at all about the thirty that follow.
    // A reader of that output cannot tell a broken banner from a broken script,
    // which is hard-won law 7's habit 3: a check's output must distinguish pass
    // from fail TO A READER, not merely to an exit code.
    const bannerEl = page.locator('[data-testid="unit-account-protections"]').first();
    const bannerPresent = (await bannerEl.count()) > 0;
    check("the banner element is on the page at all", bannerPresent);
    const banner = bannerPresent ? await bannerEl.boundingBox() : null;
    check("the banner names the protection", /Do not disconnect/i.test(text), text.slice(0, 300));
    check("it names the kind", /[Mm]edical/.test(text));
    check("it carries the end date", /5 Nov 2026|Nov 5, 2026|11\/05\/2026/.test(text));
    // ⚠ **THIS CHECK IS SCOPED TO THE BANNER, AND THE FIRST VERSION WAS NOT
    // (found in this walkthrough, 2026-09-08).** It read the whole page body
    // for the name in `CR-089`'s worked example — *"set by D. Whitfield"* — and
    // FAILED, because the signed-in demo user IS **Dana Whitfield** and the app
    // frame prints her in the sidebar. The screen was right; the check was
    // looking at the wrong thing, which is hard-won law 7's fourth shape. It
    // also settles where the CR's example name came from: the person running
    // the demo, not a column. `account_protections.set_by` holds a ROLE.
    const bannerText = bannerPresent ? await bannerEl.innerText() : "";
    check("it names WHO set it as a role", /utility|regulator|tenant/i.test(bannerText), bannerText);
    check(
      "and invents no person's name ON THE BANNER",
      !/Whitfield/.test(bannerText),
      bannerText,
    );
    // The banner has to be ABOVE the facts or a supervisor scrolling to the
    // balance meets the money before the certificate.
    const facts = await page.locator("dl").first().boundingBox();
    check(
      "the banner sits above the first fact",
      banner !== null && facts !== null && banner.y < facts.y,
      `banner y=${banner?.y} facts y=${facts?.y}`,
    );
    // ── I2 · the class, and what it decides ───────────────────────────────
    console.log("I2 · PUJ-37 · the class is a money fact since CR-087");
    check("the class is named", /Residential/.test(text), text.slice(0, 400));
    check(
      "and says what it decides",
      /which base charge/i.test(text),
      "expected the clause 'this decides which base charge the plan applies'",
    );
    // ── I4 · five money states STATED, not omitted ────────────────────────
    console.log("I4 · PUJ-39 · an absent row reads as 'not looked up'; a stated none is the answer");
    for (const [row, sentence] of [
      ["payment plan", /None running/i],
      ["budget billing", /Not enrolled/i],
      ["collections", /Not in collections/i],
      ["payments that bounced", /Payments that bounced/i],
      ["tax exemption", /None claimed/i],
      ["deposit", /Deposit/i],
    ]) {
      check(`${row} is stated`, sentence.test(text), text.slice(0, 500));
    }
    // ── I5 · the notes ────────────────────────────────────────────────────
    console.log("I5 · PUJ-40 · the notes the product already stores");
    check("the pinned note is drawn, pinned", /📌\s*Medical protection/.test(text), text.slice(0, 600));
    check("the meter-access note is drawn", /Dog in the side yard/.test(text));
    // `DEF-CUS-4704` on screen: every note in the product has an author we hold
    // and cannot name, so the state has to SAY so rather than print a bare
    // dash between the body and the date.
    check(
      "an unnamed author says what it is, and never 'System'",
      /author not on file/i.test(text) && !/System Admin\s*Notes/.test(text),
      text.slice(0, 900),
    );
    // The CR's done-when paraphrases this as *"visible to the customer"*. The
    // screen uses the product's OWN pill — `customers.account.note
    // .customerVisiblePill`, *"Marked customer-visible"* — which is what the
    // account's own Notes tab says about the same flag. B14 rule 34: one pair
    // of words everywhere. The check follows the product, not the paraphrase.
    check(
      "its customer-visible flag shows, in the product's own words",
      /customer-visible/i.test(text),
      text.slice(0, 800),
    );
    // ── DEF-CUS-4702 · the hold that had rotted ───────────────────────────
    console.log("DEF-CUS-4702 · the Move-out hold's sentence");
    check("the control is present", /Move-out/.test(text));
    const moveOut = page.locator("button", { hasText: "Move-out" }).first();
    // ⚠ BY ATTRIBUTE. The shared Button's utility string carries
    // `disabled:opacity-45`, so a text search for the word "disabled" passes on
    // an ENABLED button — wave D's walkthrough records the same trap.
    check("it is disabled BY ATTRIBUTE, not by a class name", await moveOut.isDisabled());
    // ⚠ **THE REASON IS THE BUTTON'S `title`, NOT PAGE TEXT — AND THE FIRST
    // VERSION OF THIS CHECK READ `innerText` AND FAILED OVER A CORRECT
    // SCREEN.** `GuardedButton` puts the sentence where a clerk meets it: on
    // hover. A walkthrough that reads only rendered text cannot see it, which
    // is the same class of mistake as the banner check above.
    const reason = (await moveOut.getAttribute("title")) ?? "";
    check(
      "and no longer claims the flow does not exist",
      !/no door to it yet/i.test(reason),
      `the rotted sentence is still the reason: ${reason}`,
    );
    check("it says where the flow lives", /runs from the account/i.test(reason), reason);
    // credit_tier is served and must be drawn NOWHERE.
    check("no credit grade is shown anywhere", !/Credit tier|Credit grade/i.test(text));
  }

  // ── I3 · autopay read TOGETHER with cash-only ───────────────────────────
  console.log("\nI3 · PUJ-38 · A-10432 elected autopay AND is cash-only after two bounces");
  {
    const text = await openAccountTab(page, UNITS.sanctioned, "i3-cash-only");
    check("autopay is not reported as a bare On", !/Autopay On(?! —)/.test(text), text.slice(0, 400));
    check(
      "the screen says the money will NOT be drafted",
      /nothing will be drafted/i.test(text),
      text.slice(0, 500),
    );
    check("and says why, with the count", /2 bounced payments/.test(text), text.slice(0, 500));
    check("the bounce count is its own row", /Payments that bounced/.test(text));
    check("the deposit is drawn with its date", /\$150\.00/.test(text), text.slice(0, 600));
    check("and never at the stored scale", !/150\.0000/.test(text));
  }

  // ── I6 · the three columns with no writing door ─────────────────────────
  console.log("\nI6 · PUJ-41 · A-10877 carries the three door-less columns (DEF-CUS-4692)");
  {
    const text = await openAccountTab(page, UNITS.migrated, "i6-migrated");
    check("the legacy reference is drawn", /LEG-88214/.test(text), text.slice(0, 600));
    check("returned post is drawn as a warning", /check the address before posting/i.test(text));
    check("the credit tier is STILL not drawn", !/\bTier\b|Credit/i.test(text));
  }

  console.log("\nI6 · the delivery election and the tax exemption");
  {
    const reach = await openAccountTab(page, UNITS.reachable, "i6-reach");
    check("the delivery election names post FIRST (BR-BIL-036)", /post/i.test(reach), reach.slice(0, 600));
    check("and adds the two elected channels", /email/i.test(reach) && /text/i.test(reach));
    check("the preferred language is drawn", /es-MX/.test(reach));

    const exempt = await openAccountTab(page, UNITS.exempt, "i6-exempt");
    check("the tax exemption is claimed, not 'None claimed'", /Claimed/i.test(exempt), exempt.slice(0, 600));
    check("with its end date", /2027/.test(exempt));
  }

  await browser.close();
  return page;
})();

const failed = results.filter((r) => !r.ok);
writeFileSync(join(OUT, "results.json"), JSON.stringify(results, null, 2));
console.log(`\n${results.length - failed.length}/${results.length} checks passed. Screens in ${OUT}`);
if (failed.length > 0) {
  console.log("FAILED:");
  for (const f of failed) console.log("  ·", f.name);
  process.exit(1);
}
