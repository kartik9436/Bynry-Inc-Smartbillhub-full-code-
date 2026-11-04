// ── Trace ──────────────────────────────────────────────
// Change:  **`REQ-03` six steps into four — PO approval 2026-09-29.** Lane
//          SCREEN-A, tasks 5–7: step 1 *The applicant* + Documents, step 2
//          *Property*. Drawings:
//          `05-prototype/new-request-four-steps-2026-09-29/`.
// Defects: `DEF-CUS-7850` (`+ Premises` in both states, a door out of the
//          wizard) · `DEF-CUS-7851` (two document buttons for one act)
// Rules:   CLAUDE.md hard-won law 6 (*"diff the running app — no gate looks at
//          rendered output"*) · law 7 (a check's output must distinguish pass
//          from fail TO A READER) · B14 rule 33 · the STAFF widths, 1440 and
//          1280, plus 420 because the approved drawings carry one.
// ───────────────────────────────────────────────────────
//
//   node 10-scripts/req03_four_step_screen_a_shots.mjs
//
// Env: SMOKE_BASE (http://127.0.0.1:8080) · SMOKE_TENANT · SMOKE_EMAIL ·
//      SMOKE_PASSWORD · SHOT_OUT · PW_CHROME
//
// ⚠ **IT PHOTOGRAPHS AND IT ALSO ASSERTS, BECAUSE A PNG CANNOT SHOW AN
// ABSENCE.** Three of the four things this redesign changed are things that
// are NO LONGER THERE — the second document button, `+ Premises`, and the five
// empty mailing boxes — and a photograph of a correct screen and a photograph
// of a wrong one look identical to a reader who does not know what to miss. So
// every claim is printed PASS/FAIL beside the shot it belongs to, and the
// script exits non-zero if any fails.
//
// ⚠ **NO CSS IS INJECTED, NOTHING IS HIDDEN, NO VALUE IS SUBSTITUTED.** Where a
// state cannot be reached the script SAYS SO in `00-README.txt` rather than
// skipping it — an absence with no reason beside it is indistinguishable from
// a pass (law 7's fifth shape).
import { mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:8080";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SHOT_OUT ?? "/tmp/req03-screen-a";
const EXE = process.env.PW_CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

// The staff widths B14 verifies at, plus the one the drawings also carry.
const WIDTHS = [1440, 1280, 420];

const notes = [];
let failures = 0;
const note = (line) => {
  console.log(line);
  notes.push(line);
};
function check(label, ok, detail) {
  if (!ok) failures += 1;
  note(`${ok ? "PASS" : "FAIL"}  ${label}${detail === undefined ? "" : ` — ${detail}`}`);
}

// ⚠ **`fullPage: true` DOES NOT CAPTURE THE WHOLE PAGE HERE, AND THE FIRST RUN
// PROVED IT THE HARD WAY.** The app frame scrolls in an INNER container, so the
// document itself is viewport-height and `fullPage` returns the visible slice.
// At 420 that made the co-applicant-open shot **byte-identical** to the closed
// one — two files claiming to show two states, showing one. A picture that
// cannot tell the states apart is worse than no picture (law 7).
//
// So the viewport is made tall enough for the whole screen to be IN it. The
// height is measured off the scrolling element rather than guessed, and the
// script says what it measured.
async function shot(page, name, width) {
  await page.setViewportSize({ width, height: 1200 });
  await page.waitForTimeout(400);
  const tall = await page.evaluate(() =>
    Math.min(
      6000,
      Math.max(
        1200,
        document.documentElement.scrollHeight,
        ...Array.from(document.querySelectorAll("*"))
          .filter((n) => n.scrollHeight > n.clientHeight + 4)
          .map((n) => n.scrollHeight + 120),
      ),
    ),
  );
  await page.setViewportSize({ width, height: tall });
  await page.waitForTimeout(600);
  await page.screenshot({ path: `${OUT}/${name}-${width}.png`, fullPage: true });
  note(`  shot ${name}-${width}.png (${width}x${tall})`);
}

const run = async () => {
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ executablePath: EXE });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1200 } });
  const page = await context.newPage();

  // ── sign in, through the form a clerk actually uses ──────────────────────
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(`**/${TENANT}/dashboard`, { timeout: 30000 });
  note(`signed in as ${EMAIL}`);

  // ══════════════════════════════════════════════════════════════════════
  // STEP 1 · THE APPLICANT
  // ══════════════════════════════════════════════════════════════════════
  await page.goto(`${BASE}/${TENANT}/requests/new?step=1`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("#applicant_kind", { timeout: 30000 });
  // ⚠ **WAIT FOR THE CATEGORY, NOT FOR THE FIRST CONTROL.** `Customer
  // category` is drawn only once `GET /service-requests/categories` answers;
  // reading the label order before that reported a field MISSING that was
  // merely not painted yet — the check asking the wrong question, not the
  // screen being wrong.
  await page.waitForSelector("#account_type_code", { timeout: 30000 });

  const head = (await page.locator("h1").first().innerText()).trim();
  check("step 1's page title is the drawn question", head === "Who is this request for?", head);

  const subline = await page.locator("text=/Step 1 of 4/").count();
  check("the sub-line reads `Step 1 of 4`", subline === 1, `${subline} found`);

  // THE ELEVEN, IN THE DRAWN ORDER, read off the rendered document.
  const order = await page.evaluate(() =>
    Array.from(document.querySelectorAll("label"))
      .map((n) => (n.textContent ?? "").replace(/\*/g, "").trim())
      .filter(Boolean),
  );
  const drawn = [
    "Applying as",
    "Channel",
    "Full name",
    "Email",
    "Phone",
    "Date of birth",
    "Tax ID",
    // ⚠ **`license`, NOT `licence` — THE DRAWING IS THE OUTLIER.** The PO
    // ruled American English on 2026-09-29 (*"use american english check =
    // not cheque"*) and the catalogue already says `Driver's license`. The
    // drawing's British spelling is stamped as a divergence rather than built.
    "Driver's license",
    "Social Security Number",
    "Customer category",
    "Sub-category",
  ];
  const seen = order.filter((label) => drawn.includes(label)).slice(0, drawn.length);
  check(
    "the eleven fields are in the drawn order",
    JSON.stringify(seen) === JSON.stringify(drawn),
    JSON.stringify(seen),
  );

  check(
    "`Tax ID` is drawn and refused for a person",
    (await page.locator("#tax_id").isDisabled()) &&
      (await page.locator("#tax_id").getAttribute("placeholder")) === "Companies only",
  );
  check(
    "the co-applicant fields are ABSENT before the tick",
    (await page.locator("#co_applicant_name").count()) === 0,
  );
  check(
    "ONE document button — `Add another document` is gone",
    (await page.locator("[data-doc-attach]").count()) === 1 &&
      (await page.locator("[data-doc-add]").count()) === 0,
  );
  check(
    "`Documents` carries the drawn sub-line",
    (await page.locator("text=Brought in with this request.").count()) === 1,
  );
  for (const width of WIDTHS) await shot(page, "01-applicant", width);

  // ── the co-applicant, expanded ───────────────────────────────────────────
  await page.setViewportSize({ width: 1440, height: 1200 });
  // ⚠ **CLICK THE LABEL, NOT THE INPUT.** The kit's checkbox input is
  // `sr-only` and its drawn mark intercepts the pointer, so a click on the
  // input never lands and `check({force:true})` cannot resolve it either. The
  // label is what a person presses.
  await page.click('label[for="add_co_applicant"]');
  await page.waitForSelector("#co_applicant_name", { timeout: 10000 });
  check(
    "the three co-applicant fields expand on tick, and are LIVE",
    !(await page.locator("#co_applicant_name").isDisabled()) &&
      !(await page.locator("#co_applicant_email").isDisabled()) &&
      !(await page.locator("#co_applicant_phone").isDisabled()),
  );
  for (const width of WIDTHS) await shot(page, "01b-applicant-coapplicant-open", width);
  await page.click('label[for="add_co_applicant"]');

  // ══════════════════════════════════════════════════════════════════════
  // STEP 2 · THE PROPERTY
  // ══════════════════════════════════════════════════════════════════════
  await page.goto(`${BASE}/${TENANT}/requests/new?step=2`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("#address_as_given", { timeout: 30000 });

  const head2 = (await page.locator("h1").first().innerText()).trim();
  check("step 2's page title is the drawn question", head2 === "Where is the service going?", head2);

  // ⚠ **THE EMPTY STATE IS BEFORE ANYTHING IS TYPED, AND THAT IS THE WHOLE
  // POINT OF ASKING HERE.** `evidenceRows` is built from what the CLERK
  // typed, so it stops being empty on the first keystroke. Asking after
  // filling the box measured a state the drawing does not draw.
  check(
    "`Found in Premises` is drawn, with its own sentence, before anything is typed",
    (await page.locator("text=Found in Premises").count()) === 1 &&
      (await page.locator("text=Nothing matched yet.").count()) === 1,
  );
  await shot(page, "02z-property-untouched", 1440);

  // Type an address the register does not hold — the NOT FOUND state the
  // drawing is taken in.
  await page.fill("#address_as_given", "Mark 234");
  await page.fill("#address_unit_as_given", "12");
  await page.waitForTimeout(1500);

  check(
    "`+ Premises` is absent while NOTHING matched",
    (await page.locator("text=+ Premises").count()) === 0,
  );
  check(
    "the typed address is kept word for word (BR-CUS-070)",
    (await page.locator("#address_as_given").inputValue()) === "Mark 234",
  );
  // ⚠ 2026-10-11 (`DEF-CUS-10039`, PO): with NO premise matched, City, State
  // and ZIP are TYPED — the PO restored the 2026-09-22 ruling over the
  // drawing's three locked boxes. They turn read-only only once a premise is
  // picked. And *Check address* (`DEF-CUS-10040`) is offered beside them.
  const typed = { address_city_as_given: "Sugar Land", address_state_as_given: "TX", address_postal_code_as_given: "77479" };
  for (const [id, value] of Object.entries(typed)) {
    const ro = await page.locator(`#${id}`).getAttribute("readonly");
    await page.fill(`#${id}`, value);
    check(
      `\`${id}\` is typeable while no premise matched`,
      ro === null && (await page.locator(`#${id}`).inputValue()) === value,
    );
  }
  check(
    "the Check address panel is offered while no premise is picked",
    (await page.locator("[data-request-city-check] [data-check-address]").count()) === 1,
  );
  check(
    "`Mailing address` replaces `Billing address`",
    (await page.locator("h3:text('Mailing address')").count()) === 1 &&
      (await page.locator("text=Billing address").count()) === 0,
  );
  check(
    "ticked, the mailing block PRINTS the service address",
    (await page.locator("[data-mailing-printed]").count()) === 1 &&
      (await page.locator("[data-mailing-printed]").innerText()).includes("Mark 234"),
  );
  check(
    "ticked, the five mailing boxes are not drawn at all",
    (await page.locator("#billing_line1").count()) === 0,
  );
  for (const width of WIDTHS) await shot(page, "02-property", width);

  // ── the mailing address, cleared ─────────────────────────────────────────
  await page.setViewportSize({ width: 1440, height: 1200 });
  await page.click('label[for="billing_address_same"]');
  await page.waitForSelector("#billing_line1", { timeout: 10000 });
  check(
    "cleared, the five fields expand and are LIVE",
    !(await page.locator("#billing_line1").isDisabled()) &&
      !(await page.locator("#billing_city").isDisabled()) &&
      (await page.locator("[data-mailing-printed]").count()) === 0,
  );
  for (const width of WIDTHS) await shot(page, "02b-property-mailing-expanded", width);

  // ── the FOUND state, which the drawings do not carry ─────────────────────
  // Photographed anyway: `+ Premises` drew in BOTH states and a shot of only
  // the not-found one would leave half of `DEF-CUS-7850` unphotographed.
  await page.goto(`${BASE}/${TENANT}/requests/new?step=2`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("#address_as_given", { timeout: 30000 });
  await page.fill("#address_as_given", "Balcones");
  await page.waitForTimeout(2500);
  const options = await page.locator("[data-premises-option]").count();
  if (options === 0) {
    note(
      "NOTE  the FOUND state was not reachable on this seed — no premises matched " +
        "'Balcones'. NOT a pass: the absence of `+ Premises` in the found state is " +
        "proved by the DOM test instead, which fakes a matching row.",
    );
  } else {
    check(
      "`+ Premises` is absent while something DID match",
      (await page.locator("text=+ Premises").count()) === 0,
      `${options} option(s) offered`,
    );
    await shot(page, "02c-property-premises-found", 1440);
  }

  writeFileSync(
    `${OUT}/00-README.txt`,
    [
      "REQ-03 · New Request in four steps — lane SCREEN-A, steps 1 and 2.",
      "Put these beside 05-prototype/new-request-four-steps-2026-09-29/*.png.",
      "Divergences are stamped in that folder's DIVERGENCES-steps-1-and-2.md.",
      "",
      ...notes,
      "",
      failures === 0 ? "ALL CHECKS PASSED" : `${failures} CHECK(S) FAILED`,
    ].join("\n"),
  );
  await browser.close();
  note(failures === 0 ? "ALL CHECKS PASSED" : `${failures} CHECK(S) FAILED`);
  process.exit(failures === 0 ? 0 : 1);
};

run().catch((error) => {
  console.error(error);
  process.exit(2);
});
