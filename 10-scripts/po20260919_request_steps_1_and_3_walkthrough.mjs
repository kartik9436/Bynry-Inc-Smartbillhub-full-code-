// ── THE NEW-REQUEST WIZARD'S STEPS 1 AND 3, WALKED IN A BROWSER ────────────
//
// ⚠ **UPDATED 2026-10-11 TO THE FOUR-STEP WIZARD** (PO approval 2026-09-29): the
// file name keeps its old `steps_1_and_3`, but the address step it walks is now
// STEP 2 · Property — see that section's own note for what moved.
//
// `CR-094-BRC01` · the Accounts blueprint's **entry 06, pages 75–77**, read AS
// PAGE IMAGES at scale 2 and 5 (B14 rule 42). Run it after any change to
// `ServiceRequestCapturePage.tsx`.
//
// **WHAT IT IS FOR.** No gate in this repo reads rendered output, and nearly
// half of everything that goes wrong on a screen here is *the screen does not
// match its design*. This walk is the check that reads the screen: it asserts
// the drawn LABELS, the drawn ORDER, the drawn two-column PAIRING, the drawn
// table's three rows and their confidence words, and — where a signed rule
// beats the drawing — it pins the divergence so nobody quietly "fixes" it back.
//
// ⚠ **IT REFUSES A STALE BUILD, AND THAT GUARD IS THE POINT** (borrowed from
// `plan_wizard_seven_walkthrough.mjs`, which was one message from reporting
// three landed fixes as absent). Nothing on the page says how old the bundle
// is; `tsc`, the suites and every gate are green either way, because none of
// them look at `dist/`.
//
// ⚠ **IT WRITES EXACTLY ONE DRAFT, AND IT TAGS IT.** Proving that
// `units_on_property` reaches the SERVER cannot be done by reading the screen —
// the screen is where the wrong answer would look right. So the walk fills the
// server's own minimum, lets the wizard PATCH, and the row is then removed by
// `po20260919_request_steps_purge.py`, which deletes by this run's tag and
// nothing else. **Run the purge, or the next person's beta lies to them.**
// The tag is printed at the end.
//
//   REQ_WALK_BASE     default http://127.0.0.1:8932
//   REQ_WALK_TENANT   default brazosbend
//   REQ_WALK_EMAIL    default dana@brazosbendutilities.com
//   REQ_WALK_PASSWORD default S3cure!passw0rd
//   REQ_WALK_CHROME   default /opt/pw-browsers/chromium-1194/chrome-linux/chrome
//     (the pinned @playwright/test version does not match the preinstalled
//      browser in this container, so the path is passed explicitly — see
//      CLAUDE.md's environment note; never run `playwright install` here.)
//   REQ_WALK_SHOTS    default ./ — where the two PNGs land (req-step1, req-step2)
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");
import { execSync } from "node:child_process";
import { statSync } from "node:fs";

const BASE = process.env.REQ_WALK_BASE || "http://127.0.0.1:8932";
const T = process.env.REQ_WALK_TENANT || "brazosbend";
const EMAIL = process.env.REQ_WALK_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.REQ_WALK_PASSWORD || "S3cure!passw0rd";
const CHROME =
  process.env.REQ_WALK_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const SHOTS = process.env.REQ_WALK_SHOTS || ".";
const TAG = `W1AND3-${Date.now().toString().slice(-6)}`;

// ── the staleness refusal ──────────────────────────────────────────────────
const built = statSync("07-frontend/dist/index.html").mtime;
const newestSrc = new Date(
  execSync("git log -1 --format=%cI -- 07-frontend/src").toString().trim(),
);
if (built < newestSrc) {
  console.error(
    `REFUSED: dist/ was built ${built.toISOString()} but 07-frontend/src has a\n` +
      `commit at ${newestSrc.toISOString()}. Run \`npx vite build\` first.\n` +
      `A walk against a stale bundle reports absent features that are present.`,
  );
  process.exit(2);
}

const R = [];
const ok = (n, c, d = "") => R.push(`${c ? "PASS" : "FAIL"} · ${n}${d ? " · " + d : ""}`);

const b = await chromium.launch({ executablePath: CHROME });
const p = await b.newPage({ viewport: { width: 1280, height: 1400 } });

// ⚠ **A CRASH MUST STILL PRINT WHAT PASSED.** Half of this walk types into
// controls that only exist once the screen is right — `#units_on_property`,
// the billing box — so on a build where they are absent playwright throws and
// a bare top-level script would exit with a stack trace and no findings at all.
// The red proof for this walk was run exactly that way and it is what the
// `finally` below is for: the run against the 2026-09-15 build reports the
// twelve things it managed to check and then the control it could not find.
try {
await p.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
await p.fill("#signin-email", EMAIL);
await p.fill("#signin-password", PASSWORD);
await Promise.all([
  p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
  p.click('button[type="submit"]'),
]);

// ═══════════════════════════════════════════════════════════════════════════
// STEP 1 · Customer — drawn p075 (head) and p076 (fields)
// ═══════════════════════════════════════════════════════════════════════════
await p.goto(`${BASE}/${T}/requests/new?step=1`, { waitUntil: "networkidle" });
await p.waitForTimeout(1500);

// ── the label, and the sentence it replaced ────────────────────────────────
// ⚠ *"`Channel` is on screen"* passes on a page that ALSO still asks the old
// question, so both halves are asserted.
const s1text = await p.evaluate(() => document.body.innerText);
const channelLabel = await p.evaluate(
  () => document.querySelector('label[for="channel"]')?.textContent?.trim() ?? "",
);
ok("step1 · the channel label reads Channel", channelLabel === "Channel", channelLabel);
ok(
  "step1 · the old question is gone",
  !/How did this reach us\?/.test(s1text),
);

// ── Applying as is a DROPDOWN (PO 2026-09-19) ─────────────────────────────
// ⚠ *"a control called Applying as exists"* passed on the SEGMENTED pair too,
// so this asserts the ELEMENT and its options.
const kind = await p.evaluate(() => {
  const el = document.querySelector("#applicant_kind");
  if (!el) return null;
  return {
    tag: el.tagName,
    options: [...el.querySelectorAll("option")].map((o) => o.textContent.trim()),
  };
});
ok("step1 · Applying as is a <select>", kind?.tag === "SELECT", kind?.tag ?? "absent");
ok(
  "step1 · it offers the two kinds and nothing else",
  JSON.stringify(kind?.options) === JSON.stringify(["A person", "A business"]),
  JSON.stringify(kind?.options),
);

// ── the drawn seven, in the drawn ORDER ───────────────────────────────────
const DRAWN = [
  "channel",
  "applicant_name",
  "applicant_email",
  "applicant_phone",
  "date_of_birth",
  "drivers_licence",
  "ssn",
];
const order = await p.evaluate((ids) => {
  const found = [...document.querySelectorAll("input,select")]
    .map((el) => el.id)
    .filter((id) => ids.includes(id));
  return found;
}, DRAWN);
ok(
  "step1 · the seven drawn fields are in the drawn order",
  JSON.stringify(order) === JSON.stringify(DRAWN),
  JSON.stringify(order),
);

// ── the drawn two-column PAIRING ──────────────────────────────────────────
// ⚠ *"the fields are all present"* passes on the three-across grid this
// replaced, which put Phone beside Email on row one and moved every field
// after it. Rows are compared by the input's own top edge.
const rows = await p.evaluate((ids) => {
  const top = {};
  for (const id of ids) {
    const el = document.getElementById(id);
    top[id] = el ? Math.round(el.getBoundingClientRect().top) : null;
  }
  return top;
}, DRAWN);
const sameRow = (a, c) => rows[a] !== null && Math.abs(rows[a] - rows[c]) <= 4;
// ⚠ 2026-10-11: the pairing is the FOUR-STEP drawing's (PO approval
// 2026-09-29, `05-prototype/new-request-four-steps-2026-09-29/`), not p076's:
// `Applying as` opens the grid beside `Channel`, so every pair moved one
// field on — Name·Email, Phone·Date of birth, Tax ID·Driver's license, then
// SSN beside Customer category. `req03_four_step_screen_a_shots.mjs` asserts
// the eleven-field ORDER; this asserts the rows.
rows.applicant_kind = await p.evaluate(() => {
  const el = document.getElementById("applicant_kind");
  return el ? Math.round(el.getBoundingClientRect().top) : null;
});
rows.tax_id = await p.evaluate(() => {
  const el = document.getElementById("tax_id");
  return el ? Math.round(el.getBoundingClientRect().top) : null;
});
rows.account_type_code = await p.evaluate(() => {
  const el = document.getElementById("account_type_code");
  return el ? Math.round(el.getBoundingClientRect().top) : null;
});
ok("step1 · Applying as and Channel share a row", sameRow("applicant_kind", "channel"));
ok("step1 · Full name and Email share a row", sameRow("applicant_name", "applicant_email"));
ok("step1 · Phone and Date of birth share a row", sameRow("applicant_phone", "date_of_birth"));
ok("step1 · Tax ID and Driver's licence share a row", sameRow("tax_id", "drivers_licence"));
ok("step1 · SSN and Customer category share a row", sameRow("ssn", "account_type_code"));
ok("step1 · Full name is BELOW Channel, not beside it", rows.applicant_name > rows.channel);

// ── B14 rule 33: no rationale under any of the seven ──────────────────────
const helps = await p.evaluate(
  (ids) => ids.filter((id) => document.getElementById(`${id}-help`) !== null),
  DRAWN,
);
ok("step1 · not one of the seven carries a help line", helps.length === 0, helps.join(","));
ok(
  "step1 · no storage promise is printed on the step",
  !/[Ss]tored encrypted/.test(s1text),
);
ok(
  "step1 · no reason-for-the-name sentence is printed",
  !/No applicant on file/.test(s1text) && !/there is no applicant to name/.test(s1text),
);

// ── the co-applicant is ONE checkbox ──────────────────────────────────────
const co = await p.evaluate(() => {
  const box = document.querySelector("#add_co_applicant");
  return {
    isCheckbox: box?.type === "checkbox",
    label: document.querySelector('label[for="add_co_applicant"]')?.textContent?.trim(),
  };
});
ok("step1 · Add a co-applicant is a checkbox", co.isCheckbox === true);
ok("step1 · and it is labelled as drawn", co.label === "Add a co-applicant", co.label);
ok(
  "step1 · the heading, the pill and the note are all gone",
  !/Optional · contact only/.test(s1text) &&
    !/carry no liability/.test(s1text) &&
    !/^Co-applicant$/m.test(s1text),
);

await p.screenshot({ path: `${SHOTS}/req-step1.png`, fullPage: true });

// ═══════════════════════════════════════════════════════════════════════════
// STEP 2 · Property — the four-step wizard's (PO approval 2026-09-29)
// ═══════════════════════════════════════════════════════════════════════════
// ⚠ **UPDATED 2026-10-11. THIS WAS "STEP 3 · Addresses" (p077) WHEN WRITTEN.**
// Six steps became four on 2026-09-29, so the address step is step 2; the
// `How many units` question and its panel were removed on 2026-09-22 (PO
// report row 12), and with it the match table's `units` row and the free-text
// billing box. What is asserted now is the step as built today: City/State/ZIP
// TYPED while nothing matched and the premise's own, read-only, once one is
// picked (`DEF-CUS-10039`), *Check address* offered only while unpicked
// (`DEF-CUS-10040`), the mailing block, the evidence table, and the server.
//
// ⚠ **STEP 2 IS REACHED BY PRESSING CONTINUE, NOT BY ITS URL.** The wizard
// holds the form in component state, so `goto(?step=2)` remounts it and the
// name typed on step 1 is gone — nothing is PATCHed, and the server half of
// this walk would read a request that was never saved.
await p.fill("#applicant_name", `${TAG} Walker`);
// Customer category is step 1's own gate since the four-step redesign.
await p.selectOption("#account_type_code", { index: 1 });
await p.waitForTimeout(600);
await p.locator("button").filter({ hasText: /^Continue$/ }).first().click();
await p.waitForTimeout(1500);
ok("step2 · reached by pressing Continue", /step=2/.test(p.url()), p.url());
const head2 = (await p.locator("h1").first().innerText()).trim();
ok("step2 · the page title is the drawn question", head2 === "Where is the service going?", head2);

// ── nothing matched yet: City/State/ZIP are TYPED (DEF-CUS-10039) ─────────
await p.fill("#address_as_given", `${TAG} Nowhere Rd`);
await p.waitForTimeout(1500);
const unpicked = await p.evaluate(() =>
  ["address_city_as_given", "address_state_as_given", "address_postal_code_as_given"].map((id) => {
    const el = document.getElementById(id);
    return el ? { id, readOnly: el.readOnly, disabled: el.disabled } : { id, missing: true };
  }),
);
ok(
  "step2 · with no premise matched, City/State/ZIP are typeable",
  unpicked.every((f) => f.missing !== true && f.readOnly === false && f.disabled === false),
  JSON.stringify(unpicked),
);
await p.fill("#address_city_as_given", "Silver Creek");
ok(
  "step2 · and what is typed is kept",
  (await p.locator("#address_city_as_given").inputValue()) === "Silver Creek",
);
ok(
  "step2 · Check address is offered while no premise is picked",
  (await p.locator("[data-request-city-check] [data-check-address]").count()) === 1,
);

// ── the register search and the pick ──────────────────────────────────────
// ⚠ **THE ROW IS CHOSEN BY ITS NUMBER, NOT BY BEING FIRST.** `Mill Pond`
// matches several properties and the first answer is `P-00010`, which holds
// no units. `P-00045 · 301 Mill Pond Ln` holds six.
await p.fill("#address_as_given", "Mill Pond");
await p.waitForTimeout(2500);
const option = p.locator('[data-premises-option="P-00045"]');
ok("step2 · the register answers the search", (await option.count()) > 0);
await option.click();
await p.waitForTimeout(1500);

// A premises with units turns the unit box into the register's own picker
// (PO 2026-09-15).
const unitTag = await p.locator("#address_unit_as_given").evaluate((el) => el.tagName);
ok("step2 · a premises with units offers the register's own unit picker", unitTag === "SELECT", unitTag);
if (unitTag === "SELECT") {
  await p.selectOption("#address_unit_as_given", { index: 1 });
} else {
  await p.fill("#address_unit_as_given", "Unit 1");
}
await p.waitForTimeout(1200);

const picked = await p.evaluate(() => document.querySelector("[data-premises-picked]")?.getAttribute("data-premises-picked") ?? null);
ok("step2 · the picked premises is named by its number", picked === "P-00045", picked ?? "absent");

// ── picked: City/State/ZIP are the PREMISE'S, read-only (hard rule 8) ─────
// ⚠ **THIS PINS HARD RULE 8 / `BR-MET-1161`.** Once a premise is picked the
// address is the premise's and nowhere else: the three boxes show its walked
// values and cannot be typed into. If somebody makes them editable here, this
// goes RED rather than letting a fourth address home land quietly.
const locality = await p.evaluate(() =>
  ["address_city_as_given", "address_state_as_given", "address_postal_code_as_given"].map((id) => {
    const el = document.getElementById(id);
    return el ? { id, readOnly: el.readOnly, value: el.value } : { id, missing: true };
  }),
);
ok(
  "step2 · picked, City/State/ZIP are read-only",
  locality.every((f) => f.readOnly === true),
  JSON.stringify(locality),
);
ok(
  "step2 · and they show the premise's own city, state and ZIP",
  JSON.stringify(locality.map((f) => f.value)) === JSON.stringify(["Silver Creek", "TX", "78611"]),
  JSON.stringify(locality.map((f) => f.value)),
);
ok(
  "step2 · Check address goes once a premise is picked",
  (await p.locator("[data-request-city-check]").count()) === 0,
);
const s2after = await p.evaluate(() => document.body.innerText);

// ── the mailing address: printed while ticked ─────────────────────────────
const printed = p.locator("[data-mailing-printed]");
ok(
  "step2 · ticked, the mailing block PRINTS the service address",
  (await printed.count()) === 1 && /301 Mill Pond Ln/.test(await printed.innerText()),
);
await p.click('label[for="billing_address_same"]');
await p.waitForSelector("#billing_line1", { timeout: 10000 });
ok(
  "step2 · cleared, the mailing fields expand and are live",
  !(await p.locator("#billing_line1").isDisabled()) && (await printed.count()) === 0,
);
// back on, so the draft this walk saves carries the drawn default
await p.click('label[for="billing_address_same"]');
await p.waitForTimeout(400);

// ── the evidence table ────────────────────────────────────────────────────
// ⚠ *"the match table exists"* passes on an EMPTY one. Every cell is read.
const table = await p.evaluate(() =>
  [...document.querySelectorAll('[data-table="match-evidence"] tbody tr')].map((tr) => ({
    key: tr.getAttribute("data-match-row"),
    cells: [...tr.querySelectorAll("td")].map((td) => td.textContent.trim()),
    confidence: tr.querySelector("[data-confidence]")?.getAttribute("data-confidence"),
  })),
);
const addressRow = table.find((r) => r.cells[1] === "P-00045");
ok(
  "step2 · Found in Premises names the picked premises with its confidence",
  addressRow !== undefined && addressRow.cells[0] === "301 Mill Pond Ln" && addressRow.cells[2] !== "",
  JSON.stringify(table),
);

// ── what was removed stays removed ────────────────────────────────────────
ok(
  "step2 · the unit-count question is gone (PO 2026-09-22)",
  (await p.locator("#units_on_property").count()) === 0,
);
const radios = await p.evaluate(() => document.querySelectorAll('input[name="property_type"]').length);
ok("step2 · the property-type radios are gone", radios === 0, `${radios} radio(s)`);
ok(
  "step2 · and so is their heading and their explanations",
  !/Property details/.test(s2after) && !/Standalone · owner occupied/.test(s2after),
);

await p.screenshot({ path: `${SHOTS}/req-step2.png`, fullPage: true });

// ── does the pick actually REACH THE SERVER? ─────────────────────────────
// The screen is where a wrong answer looks right, so this goes forward and
// lets the wizard PATCH, then reads the request back through the API.
await p.locator("button").filter({ hasText: /^Continue$/ }).first().click();
await p.waitForTimeout(2500);
const saved = await p.evaluate(
  async ([tenant, tag]) => {
    const list = await (
      await fetch(`/api/${tenant}/service-requests?segment=all&per=200`, {
        headers: { Accept: "application/json" },
      })
    ).json();
    const rows = list.data?.results ?? list.results ?? [];
    // ⚠ the list row calls it `applicant`, not `applicant_name`.
    const mine = rows.find((r) => (r.applicant ?? "").startsWith(tag));
    if (!mine) return { count: rows.length, mine: null };
    const detail = await (
      await fetch(`/api/${tenant}/service-requests/${mine.id}`, {
        headers: { Accept: "application/json" },
      })
    ).json();
    const loc = (detail.data ?? detail).location_and_services;
    return {
      count: rows.length,
      mine: {
        address: loc.address_as_given,
        property_type: loc.property_type,
        unit: loc.address_unit_as_given,
      },
    };
  },
  [T, TAG],
);
ok("server · the draft was saved at all", saved.mine !== null);
ok(
  "server · the address reached the column",
  /Mill Pond/.test(saved.mine?.address ?? ""),
  saved.mine?.address ?? "",
);
// ⚠ **THE OTHER HALF OF THE RADIOS' REMOVAL**: a request captured here
// carries NO property type. If somebody puts the control back without saying
// so, this goes red rather than the column quietly starting to fill again.
ok(
  "server · a request captured here now carries no property type",
  saved.mine?.property_type === null,
  String(saved.mine?.property_type),
);
// ⊕ The unit PICKER, proved by what it stored: the register's own `unit_no`,
// not something a clerk typed (`DEF-CUS-5873`).
ok(
  "server · the unit came from the register, not from free text",
  /^[A-Z]+-U-\d+$/.test(saved.mine?.unit ?? ""),
  saved.mine?.unit ?? "",
);
console.log(`requests visible after the walk: ${saved.count}`);

} catch (err) {
  ok("the walk ran to the end", false, String(err).split("\n")[0]);
} finally {
  console.log("\n" + R.join("\n"));
  console.log(
    `\n${R.filter((r) => r.startsWith("PASS")).length} PASS · ` +
      `${R.filter((r) => r.startsWith("FAIL")).length} FAIL`,
  );
  console.log(`\nTAG=${TAG}  ← purge with po20260919_request_steps_purge.py`);
  await b.close();
  process.exit(R.some((r) => r.startsWith("FAIL")) ? 1 : 0);
}
