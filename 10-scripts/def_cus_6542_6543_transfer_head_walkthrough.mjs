// ── THE TRANSFER WIZARD'S PAGE HEAD, ON ALL FIVE STEPS ───────────────────────
//
// ── Trace ────────────────────────────────────────────────────────────────────
// Defects: `DEF-CUS-6542` — the wizard printed step 1's `<h1>` on all five
//          steps, so a clerk standing on the buyer step was told to *"Find the
//          account, and who is selling"*. The drawing titles each step.
//          `DEF-CUS-6543` — the shared applicant capture drew its *One
//          identifier* heading and its six-word instruction over an EMPTY
//          group whenever no customer kind was stated.
// Drawing: `05-prototype/02 Accounts Menu Blueprint.pdf`, the 281-page edition,
//          **read AS IMAGES at scale 2** (B14 rule 42) — the five step screens
//          are PDF pages **127, 128, 129, 130 and 131**. Each draws the same
//          three-line head and nothing else: the `TRANSFER` kicker, the 32px
//          title, and `Step N of 5 · <rail label>`.
// Rules:   B14 rule 33 (a HEADING ≤ 3 words and no sentence) · rule 40 (the
//          page-head title is 32px) · rule 41 (the product matches the drawing) ·
//          rule 42 (build from the image) · rule 44 (our UI standard decides
//          construction) · CLAUDE.md hard-won laws 2, 6, 7
//
// ⚠ **AMENDED 2026-09-24 (lane TRF-CAP): THE FIVE TITLES ARE NO LONGER THE DRAWN
// STRINGS.** PO ruling, verbatim: ***"4 · The five transfer headings - b
// Shorten all five to the cap"***. They ran 7 · 4 · 4 · 5 · 6 words against rule
// 33's three and are now 3 · 2 · 2 · 2 · 3, so this file now checks the CAP and
// the no-sentence half beside the string itself. **The move-out's four shortfall
// path names are untouched — the PO ruled *"b) Leave as drawn"* on those the
// same morning and both rulings stand.**
// Screens: `TRF-02` (S89), steps 1–5
// ─────────────────────────────────────────────────────────────────────────────
//
// ⚠ **IT RUNS IN THE TREE IT IS IN** (`DEF-CUS-6028`): `ROOT` comes from
// `import.meta.url`, never a typed path, so a worktree drives ITS OWN bundle.
//
// ⚠ **IT WRITES NOTHING.** No sale is committed and no customer is minted. The
// five steps are reached by URL (`?step=N`), which is how a parked draft
// resumes, and every assertion is a READ of rendered output.
//
// ⚠ **EVERY CHECK BELOW WAS SHOWN RED ON THE UNFIXED BUNDLE BEFORE IT WAS
// TRUSTED GREEN** (hard-won law 7), and the before/after shots are in `SHOTS`.
//
// ⚠ **THE TITLE IS READ FROM THE PAGE HEAD'S OWN `<h1>`, NEVER FROM BODY
// TEXT.** Four of the five drawn titles are ALSO drawn as a section heading
// further down the same step — *"The date of sale"* and *"What the buyer takes
// on"* both appear twice — so `body.includes(title)` is true on a step whose
// head says something else entirely. That is the fault this file exists for,
// wearing the clothes of a pass.
//
//   THW_BASE    default http://127.0.0.1:4482 — the SPA join (`server.mjs` over
//               a `vite build`). The vite DEV server has no `/api` proxy.
//   THW_TENANT  default brazosbend
//   THW_SHOTS   default the scratchpad's trf-titles folder
//   THW_TAG     `before` | `after` — names the screenshot set
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..");
const require = createRequire(path.join(ROOT, "07-frontend/package.json"));
const { chromium } = require("playwright");

const BASE = process.env.THW_BASE || "http://127.0.0.1:4482";
const T = process.env.THW_TENANT || "brazosbend";
const EMAIL = process.env.THW_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.THW_PASSWORD || "S3cure!passw0rd";
const CHROME = process.env.THW_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const TAG = process.env.THW_TAG || "before";
const SHOTS =
  process.env.THW_SHOTS ||
  "/tmp/claude-0/-home-user-SMARTBillHub/6ba8cd67-91ed-5ae1-ac39-8519d4343c20/scratchpad/trf-titles";
mkdirSync(`${SHOTS}/${TAG}`, { recursive: true });

let pass = 0, fail = 0;
const failures = [];
function ok(what, cond, detail = "") {
  if (cond) { pass += 1; console.log(`  ✓ ${what}`); }
  else { fail += 1; failures.push(`${what}${detail ? ` — ${detail}` : ""}`); console.log(`  ✗ ${what}${detail ? ` — ${detail}` : ""}`); }
  return cond;
}
const saw = (w) => console.log(`  · ${w}`);

async function shoot(p, file) {
  await p.evaluate(() => {
    window.scrollTo(0, 0);
    for (const el of Array.from(document.querySelectorAll("*"))) {
      if (el.scrollTop > 0) el.scrollTop = 0;
    }
  });
  await p.waitForTimeout(300);
  await p.screenshot({ path: `${SHOTS}/${TAG}/${file}`, fullPage: true });
}

async function signIn(p) {
  await p.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
  await p.fill("#signin-email", EMAIL);
  await p.fill("#signin-password", PASSWORD);
  await Promise.all([
    p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
    p.click('button[type="submit"]'),
  ]);
}

/** ⚠ **THE PAGE HEAD'S OWN `<h1>`, NOT THE FIRST `<h1>` ON THE DOCUMENT.**
 *  `PageHeader` is the one that carries the screen's title (B14 rule 2, one
 *  page header per screen); asking the document for `h1` would answer with
 *  whatever the app frame happens to render first. */
async function headTitle(p) {
  const el = await p.$("[data-screen='TRF-02'] h1, [data-r10='TRF-02'] h1");
  return el === null ? null : (await el.textContent()).trim();
}

/** The `Step N of 5 · <name>` line that sits under the title. */
async function stepLine(p) {
  const el = await p.$("[data-flow-footer]");
  return el === null ? null : (await el.textContent()).trim();
}

/** The head of each step. `drawn` is what the blueprint prints, read AS AN IMAGE
 *  (rule 42); `title` is what the PO ruled it shortened to on 2026-09-24; `page`
 *  is the PDF page, kept so the next lane re-opens the drawing rather than trust
 *  this list.
 *
 *  ⚠ **`title` WAS `drawn` UNTIL 2026-09-24 — PO ruling, verbatim: *"4 · The
 *  five transfer headings - b  Shorten all five to the cap"*.** B14 rule 33 caps
 *  a heading at three words; the drawn five ran 7 · 4 · 4 · 5 · 6 and were built
 *  as drawn for one day under the move-out's *"Leave as drawn"* precedent. **The
 *  move-out's four shortfall labels are NOT affected** — that ruling stands. */
const DRAWN = [
  {
    step: 1,
    page: 127,
    drawn: "Find the account, and who is selling",
    title: "Account & seller",
    rail: "Find the account",
  },
  { step: 2, page: 128, drawn: "Who is buying it", title: "The buyer", rail: "The buyer" },
  { step: 3, page: 129, drawn: "The date of sale", title: "The date", rail: "Date of sale" },
  {
    step: 4,
    page: 130,
    drawn: "What the buyer takes on",
    title: "The money",
    rail: "What they take on",
  },
  {
    step: 5,
    page: 131,
    drawn: "Review — one account, one new owner",
    title: "Review & confirm",
    rail: "Review & confirm",
  },
];

/** Whitespace-separated tokens — `&` counts as a word, the stricter reading. */
const words = (s) => String(s).trim().split(/\s+/).filter(Boolean).length;

(async () => {
  const browser = await chromium.launch({ executablePath: CHROME, args: ["--no-sandbox"] });
  //: 1440 wide is the design target; the height is deliberately tall because
  //: the app scrolls an INNER container and `fullPage` otherwise captures from
  //: wherever that container is sitting.
  const page = await browser.newPage({ viewport: { width: 1440, height: 2200 } });
  try {
    await signIn(page);

    console.log("\n── DEF-CUS-6542 · THE TITLE ON EACH OF THE FIVE STEPS ───────");
    const seen = [];
    for (const want of DRAWN) {
      await page.goto(`${BASE}/${T}/transfers/new?step=${want.step}`, { waitUntil: "networkidle" });
      await page.waitForTimeout(700);
      const got = await headTitle(page);
      const line = await stepLine(page);
      seen.push(got);
      await shoot(page, `step-${want.step}-head.png`);
      saw(`step ${want.step}: h1 = ${JSON.stringify(got)}`);
      saw(`step ${want.step}: ${JSON.stringify(line)}`);
      ok(
        `step ${want.step}'s title is the ruled one (drawn on p${want.page})`,
        got === want.title,
        `head says ${JSON.stringify(got)}, the ruling says ${JSON.stringify(want.title)}`,
      );
      //: B14 rule 33, both halves, on the string a clerk actually reads. The
      //: cap alone would pass *"Sold. Now who?"* — three words, two sentences.
      ok(
        `step ${want.step}'s title is within rule 33's 3-word heading cap`,
        got !== null && words(got) <= 3,
        `${JSON.stringify(got)} is ${words(got)} words`,
      );
      ok(
        `step ${want.step}'s title is a name, not a sentence (rule 33)`,
        got !== null && !/[.!?]$/.test(got) && !/[,;:—]/.test(got),
        `${JSON.stringify(got)} reads as a sentence or a clause`,
      );
      ok(
        `step ${want.step}'s step line names its own step`,
        line !== null && line.includes(`Step ${want.step} of 5`) && line.includes(want.rail),
        `it says ${JSON.stringify(line)}`,
      );
    }
    //: ⚠ **THE FAULT IS A CONSTANT, SO THE SHARPEST CHECK IS DISTINCTNESS.**
    //: Five titles that are all correct are also five DIFFERENT titles; a
    //: wizard that prints one title five times fails here by arithmetic even
    //: if somebody later mistypes what the drawing says.
    ok(
      "the five titles are five different strings",
      new Set(seen).size === 5,
      `${new Set(seen).size} distinct: ${JSON.stringify(seen)}`,
    );

    //: B14 rule 40 — the page-head title is 32px on every screen, measured
    //: against the BUILT stylesheet rather than asserted off a class name.
    const px = await page.evaluate(() => {
      const h = document.querySelector("[data-r10='TRF-02'] h1");
      return h === null ? null : window.getComputedStyle(h).fontSize;
    });
    ok("the page-head title is 32px (B14 rule 40)", px === "32px", `it is ${px}`);

    console.log("\n── DEF-CUS-6543 · THE IDENTIFIER GROUP WITH NO KIND STATED ──");
    await page.goto(`${BASE}/${T}/transfers/new?step=2`, { waitUntil: "networkidle" });
    await page.waitForTimeout(700);

    //: The three identifier boxes `BR-CUS-1022` draws for a PERSON, and the
    //: one it draws for a COMPANY. With no kind stated it draws none of them,
    //: which is the rule working — the defect is the HEADING that stays.
    const boxes = ["trf_buyer_date_of_birth", "trf_buyer_ssn", "trf_buyer_drivers_licence", "trf_buyer_tax_id"];
    let anyBox = false;
    for (const id of boxes) if ((await page.$(`#${id}`)) !== null) anyBox = true;
    ok(
      "no identifier box is drawn before a kind is stated (BR-CUS-1022)",
      anyBox === false,
      "a box is drawn with no kind stated",
    );

    const headingShown = await page.evaluate(() => {
      const wanted = ["One identifier", "Un identificador", "Une pièce", "Ein Nachweis"];
      return Array.from(document.querySelectorAll("p.font-heading")).some((p) =>
        wanted.includes((p.textContent || "").trim()),
      );
    });
    const instructionShown = (await page.$("[data-identifier-instruction]")) !== null;
    await shoot(page, "step-2-no-kind-stated.png");
    saw(`heading rendered: ${headingShown} · instruction rendered: ${instructionShown}`);

    ok(
      "the 'One identifier' heading is NOT drawn over an empty group",
      headingShown === false,
      "the heading renders with no field under it",
    );
    ok(
      "the identifier instruction is NOT drawn over an empty group",
      instructionShown === false,
      "'Give one ID or a phone.' renders with no field under it",
    );

    console.log("\n── AND IT COMES BACK WITH THE FIELDS ────────────────────────");
    const person = await page.$('label.seg-opt:has-text("Person")');
    if (person !== null) {
      await person.click();
      await page.waitForTimeout(600);
      const backHeading = await page.evaluate(() => {
        const wanted = ["One identifier", "Un identificador", "Une pièce", "Ein Nachweis"];
        return Array.from(document.querySelectorAll("p.font-heading")).some((p) =>
          wanted.includes((p.textContent || "").trim()),
        );
      });
      const backInstruction = (await page.$("[data-identifier-instruction]")) !== null;
      const backBox = (await page.$("#trf_buyer_ssn")) !== null;
      await shoot(page, "step-2-person-stated.png");
      ok("stating Person draws the identifier boxes", backBox);
      ok("the heading comes back with its fields", backHeading);
      ok("the instruction comes back with its fields", backInstruction);
    } else {
      ok("the Person/Company control is on the step", false, "no segmented option found");
    }
  } finally {
    await browser.close();
  }

  console.log(`\n${pass} passed · ${fail} failed · shots in ${SHOTS}/${TAG}`);
  for (const f of failures) console.log(`  ✗ ${f}`);
  process.exit(fail === 0 ? 0 : 1);
})();
