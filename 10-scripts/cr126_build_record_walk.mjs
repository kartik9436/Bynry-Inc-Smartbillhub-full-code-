// ── Trace ──────────────────────────────────────────────
// Change:   CR-126-BRC07 — the browser walk for the NEW CONNECT BUILD RECORD,
//           built as SECTIONS on the property's Build tab.
// Rules:    CLAUDE.md hard-won law 6 — *"diff the running app against the
//           prototype: nine defects were found this way and by nothing else."*
//           NO gate in this repo reads rendered output, so this script and a
//           person are the only things that can say the screen is right ·
//           `OQ-MET-12520` option C, CONFIRMED by the PO (decision log
//           2026-09-20, `8cb9a379c`) — *"MAKE THE BUILD TAB COMPLETE"*, so the
//           record is walked AT THE PREMISES and there is deliberately no
//           `/connections/{no}` address to visit · B14 rule 42 (the drawing is
//           blueprint p098–p099, read as images)
// ───────────────────────────────────────────────────────
//
// WHAT IT CHECKS, AND WHAT IT CANNOT
// ----------------------------------
// It asserts PRESENCE, ORDER and LABELS against the drawing — the first three
// rows of the UI skill's §4 comparison. It cannot judge alignment, spacing
// rhythm or weight; a person looks at the screenshots for those.
//
// ⚠ **IT ALSO ASSERTS THE ABSENCES**, which is the half a happy-path walk
// misses. Most of this record has no server behind it yet, so "the section is
// there and says it does not know" is the CORRECT state today — and a walk
// that only looked for values would pass just as happily over a section that
// had silently stopped rendering.
//
// ⚠ **EXTENDED 2026-09-20 BY LANE NCD-7, WHEN THE RECORD READ WAS JOINED.**
// The eight new checks below are the rows that stopped being stated absences
// because real data arrived: the counted pairs, step 1's five answers, the
// parcel reference, the service tags and the two money tiles. **The absence
// checks were NOT relaxed to make room for them** — a row that still has no
// source must still say so, and the two holds must still be held, or the join
// has released something nobody ruled on. Three of the eight are NEGATIVE: no
// raw server code (`builder_developer`, `new_premise`, `storm_water`) may reach
// a clerk, because that is what a wiring lane ships when nobody looks.
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..");
const require = createRequire(path.join(ROOT, "07-frontend/package.json"));
const { chromium } = require("playwright");

const BASE = process.env.BRW_BASE || "http://127.0.0.1:8997";
const T = process.env.BRW_TENANT || "brazosbend";
const EMAIL = process.env.BRW_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.BRW_PASSWORD || "S3cure!passw0rd";
const PREMISES = process.env.BRW_PREMISES || "";
const CHROME = process.env.BRW_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const SHOTS = process.env.BRW_SHOTS || "/tmp/build-record-walk";

let pass = 0;
const failures = [];
const pageErrors = [];
const ok = (w) => { pass += 1; console.log(`  ✓ ${w}`); };
const bad = (w, saw) => { failures.push(`${w} — saw: ${saw}`); console.log(`  ✗ ${w}\n      saw: ${saw}`); };
const is = (c, w, saw) => (c ? ok(w) : bad(w, saw));

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

async function main() {
  const browser = await chromium.launch({ executablePath: CHROME });
  const ctx = await browser.newContext();
  // Staff app: 1440 is the design target, 1280 the laptop minimum. Never mobile.
  const page = await signIn(ctx, 1440);

  console.log("\n1 · the Build tab opens at the premises, which is where the PO ruled it lives");
  await page.goto(`${BASE}/${T}/premises/${PREMISES}?tab=build`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("[data-build-tab]", { timeout: 25000 });
  ok("the Build tab rendered");
  await page.screenshot({ path: `${SHOTS}/01-build-tab-1440.png`, fullPage: true });

  console.log("\n2 · the drawn header — blueprint p098, confirmed by the PO element by element");
  const head = page.locator("[data-build-record-head]");
  is(await head.count() === 1, "the record header is on the tab", `${await head.count()} found`);
  const eyebrow = await page.locator("[data-connection-no]").first().innerText().catch(() => "");
  is(/^Connection\s+\S+/i.test(eyebrow.trim()), "the eyebrow reads `Connection <no>`", eyebrow);
  // B14 rule 31 — a business number, never a uuid.
  is(!/[0-9a-f]{8}-[0-9a-f]{4}/i.test(eyebrow), "no uuid in the eyebrow (rule 31)", eyebrow);

  console.log("\n3 · the three drawn actions, in the drawn order, two of them honestly greyed");
  const actOrder = await page.locator("[data-build-record-actions] button").allInnerTexts();
  is(actOrder.length === 3, "three actions and not eight", JSON.stringify(actOrder));
  const editDisabled = await page.locator('[data-act="editDetails"]').isDisabled();
  const activateDisabled = await page.locator('[data-act="activateUnits"]').isDisabled();
  is(editDisabled, "`Edit details` is greyed (no endpoint exists)", String(editDisabled));
  is(activateDisabled, "`Activate units` is greyed (nothing can activate)", String(activateDisabled));
  // BR-SHL-025 — the refusal is READ, not only a tooltip.
  const refusal = await page.locator("[data-act-refusal]").first().innerText().catch(() => "");
  is(refusal.trim().length > 0, "the refusal is VISIBLE TEXT, not only a title", refusal);
  is(!/energi[sz]/i.test(refusal), "the refusal says activate, never energise", refusal);

  console.log("\n4 · the four drawn sections, in the drawn order");
  const sections = await page.locator("[data-build-section]").evaluateAll((els) =>
    els.map((e) => e.getAttribute("data-build-section")),
  );
  is(
    JSON.stringify(sections) === JSON.stringify(["live-state", "owner-scope", "premise", "provenance"]),
    "Live state · Owner and scope · The premise · Where it came from",
    JSON.stringify(sections),
  );

  console.log("\n5 · the premise section carries REAL data, walked from the premises");
  const premiseText = await page.locator('[data-build-section="premise"]').innerText();
  is(/Premises number/i.test(premiseText), "the premises-number row is drawn", premiseText.slice(0, 80));
  is(!/[0-9a-f]{8}-[0-9a-f]{4}/i.test(premiseText), "no uuid anywhere in the premise block", "uuid found");

  console.log("\n6 · the absences are STATED, which is most of this record today");
  const absences = await page.locator("[data-absent]").count();
  is(absences > 0, "stated absences render rather than blank gaps", `${absences} found`);
  const recordText = await page.locator("[data-build-record]").innerText();
  is(!/undefined|null|NaN/.test(recordText), "no `undefined`/`null`/`NaN` reached the screen", "found one");
  is(!/energi[sz]/i.test(recordText), "the record never says energise (PO ruling)", "found it");

  console.log("\n6b · THE JOIN — the rows that stopped being absences because data arrived");
  // `recordText` is already read in section 6 above — reused, not re-declared.
  // ⚠ **WAIT FOR THE RECORD BEFORE ASSERTING ON IT, AND FAIL LOUDLY IF IT NEVER
  // COMES.** The Build tab renders on the BUILD read and the record is a SECOND
  // round trip, so every check below races it. On 2026-09-20 this section
  // passed on one run and failed four checks on the next against an unchanged
  // app and unchanged data — the first green was LUCK, which is law 7's *what
  // would make this check pass wrongly* answered by the check on itself.
  // `[data-counted]` is drawn by the record and by nothing else, so waiting on
  // it is waiting on the join; 25 s then a REAL failure, never a silent skip.
  const joined = await page
    .waitForSelector("[data-counted]", { timeout: 25000 })
    .then(() => true)
    .catch(() => false);
  is(joined, "the record read landed and the counted pairs rendered", `waited 25s: ${joined}`);
  const tileCount = await page
    .locator("[data-build-tiles]")
    .first()
    .getAttribute("data-build-tiles")
    .catch(() => "0");
  // ⚠ **THE TILE THE RECORD ADDS ON EVERY BUILD IS `ACTIVATED`, AND THAT IS
  // WHAT IS ASSERTED — NOT A COUNT.** A count would be wrong on the demo
  // tenant: not one of its nine builds carries a quote total or a bill, so
  // QUOTED and OUTSTANDING are legitimately absent there and a `>= 4` check
  // would fail on honest data. `tiles.activated` is served on every build, so
  // its label and its `N of M` are the tile that proves the read arrived.
  const tileText = await page.locator("[data-build-tiles]").innerText().catch(() => "");
  is(Number(tileCount) >= 3, "the tile strip is drawn and carries the record's tile", tileCount);
  is(/Activated/i.test(tileText), "the ACTIVATED tile arrived with the record", tileText.slice(0, 160));
  is(/\d+\s+of\s+\d+/.test(tileText), "it reads `N of M`, counted by the server", tileText.slice(0, 160));
  const counted = await page.locator("[data-counted]").count();
  is(counted >= 2, "the two counted pairs are drawn as `N of M`", `${counted} found`);
  // ⚠ **THIS CHECK USED A REGEX THAT COULD NOT FAIL AND IT IS WRITTEN DOWN
  // BECAUSE IT WAS MINE.** It read `/\d+\s*\S*\s*\d+/` over the section's
  // text, which matches the TARGET ACTIVATION date `11/28/2026` sitting two
  // rows below — so it passed on a run where both counted rows read *not
  // counted*. Count the pairs the record draws instead, and assert the absence
  // label is gone.
  const liveText = await page.locator('[data-build-section="live-state"]').innerText();
  const livePairs = await page.locator('[data-build-section="live-state"] [data-counted]').count();
  is(livePairs === 2, "Units activated and Service points live both carry a counted pair", `${livePairs} pair(s)`);
  is(!/not counted/i.test(liveText), "neither of them still says `not counted`", liveText.slice(0, 160));

  console.log("\n6c · step 1's answers, and NEVER as the code the server stores");
  const ownerText = await page.locator('[data-build-section="owner-scope"]').innerText();
  // ⚠ THE ONE THAT MATTERS: `owner_type` and `scope` are stored as CODES.
  // A server key is not screen copy — the same trap as `units_energised`.
  for (const code of ["builder_developer", "property_owner", "landlord_", "occupier_", "new_premise", "new_units", "new_service"]) {
    is(!ownerText.includes(code), `no raw code \`${code}\` in Owner and scope`, ownerText.slice(0, 160));
  }
  is(!recordText.includes("units_energised"), "the server key `units_energised` never reaches the screen", "found it");
  // ⚠ **ONE CHECK THAT WOULD HAVE CAUGHT `DEF-MET-6453` AND THE SEVEN ABOVE
  // DID NOT.** They name codes this walk happens to know; an underscore in a
  // VALUE is the signature of ANY server token that slipped through, including
  // the ones nobody has thought of. `our_crew` sat in `How it is done` from the
  // day the shell landed and was found by looking at a screenshot.
  is(!/_/.test(ownerText), "no value in Owner and scope carries an underscore", ownerText.slice(0, 200));
  // Underscored service codes are the other half of the same fault: the tags
  // resolved a catalogue family that does not exist until `DEF-MET-6080`.
  const tagText = await page.locator("[data-build-services]").innerText().catch(() => "");
  is(!/_/.test(tagText), "the service tags are labels, not underscored codes", tagText);

  // ⚠ **THE SEVEN CHECKS ABOVE ARE NEGATIVE AND A NEGATIVE CHECK PASSES JUST
  // AS HAPPILY OVER AN EMPTY SECTION** — law 7's *ask what would make this
  // check pass wrongly*. So ask the SERVER what it sent and hold the screen to
  // it: for every step-1 code on the payload, the section must show something
  // that is not that code and is not a stated absence. It reads the record
  // through the page's own session, so it is the same door the screen used.
  // ⚠ **THE BUILD's UUID IS NOT ON THE PAGE AND MUST NOT BE** (B14 rule 31), so
  // the walk reaches it the way the screen does — through the premises' own
  // build read — rather than by scraping an id the clerk should never see.
  const served = await page.evaluate(async () => {
    const [, tenant, , premisesId] = location.pathname.split("/");
    const b = await fetch(`/api/${tenant}/premises/${premisesId}/build`, {
      credentials: "same-origin",
    });
    if (!b.ok) return null;
    const id = (await b.json())?.build?.id;
    if (!id) return null;
    const r = await fetch(`/api/${tenant}/connections/${id}/record`, { credentials: "same-origin" });
    return r.ok ? await r.json() : null;
  });

  if (served === null) {
    console.log("      (the record read could not be fetched from the page — codes checked negatively only)");
  } else {
    const codes = [served.owner_and_scope.owner_type, served.owner_and_scope.scope].filter(
      (one) => one !== null && one !== "",
    );
    const absent = await page.locator('[data-build-section="owner-scope"] [data-absent]').count();
    const rows = await page.locator('[data-build-section="owner-scope"] dt').count();
    is(codes.length > 0, "the server sent at least one step-1 code to label", JSON.stringify(codes));
    is(absent < rows, "Owner and scope is not six stated absences — values arrived", `${absent} absent of ${rows}`);
    for (const code of codes) {
      is(!ownerText.includes(code), `the code \`${code}\` was LABELLED, not printed`, ownerText.slice(0, 200));
    }
  }

  console.log("\n6d · the premise block's ninth row, which no host has ever held");
  is(/Parcel|GIS/i.test(premiseText), "the parcel-or-GIS row is drawn", premiseText.slice(0, 120));

  console.log("\n6e · money — a null is `nobody priced it` and is NEVER $0.00");
  // A build whose quote nobody worked out owes an UNKNOWN amount. `$0.00` on
  // the OUTSTANDING tile tells a clerk a debt has been settled (`DEF-127`).
  // On the demo tenant no build has a bill, so the honest state is that BOTH
  // money tiles are ABSENT. `$0.00` in their place would be the defect.
  is(!/\b0\.00\b/.test(tileText), "no $0.00 standing in for a null money figure", tileText.slice(0, 160));

  console.log("\n7 · the other five acts are one click away, not deleted");
  const more = page.getByText("More actions", { exact: false }).first();
  is(await more.count() > 0, "the More-actions disclosure is present", "absent");
  await more.click();
  await page.waitForTimeout(300);
  const acts = await page.locator("[data-build-actions] [data-act]").count();
  is(acts === 8, "all eight acts survive behind it", `${acts} found`);
  await page.screenshot({ path: `${SHOTS}/02-more-actions-open.png`, fullPage: true });

  console.log("\n8 · 1280, the laptop minimum — nothing clipped, no sideways scroll");
  const narrow = await signIn(ctx, 1280);
  await narrow.goto(`${BASE}/${T}/premises/${PREMISES}?tab=build`, { waitUntil: "domcontentloaded" });
  await narrow.waitForSelector("[data-build-tab]", { timeout: 25000 });
  const overflow = await narrow.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
  );
  is(!overflow, "no horizontal page scroll at 1280", `scrollWidth overflow: ${overflow}`);
  await narrow.screenshot({ path: `${SHOTS}/03-build-tab-1280.png`, fullPage: true });

  console.log(`\n  page errors: ${pageErrors.length}`);
  for (const e of pageErrors) console.log(`    ${e}`);
  console.log(`\n${pass} passed, ${failures.length} failed`);
  for (const f of failures) console.log(`  ✗ ${f}`);
  await browser.close();
  process.exit(failures.length === 0 && pageErrors.length === 0 ? 0 : 1);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
