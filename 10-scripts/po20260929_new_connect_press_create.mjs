#!/usr/bin/env node
// ── po20260929_new_connect_press_create.mjs ─────────────────────────────────
//
// WALK THE NEW CONNECT WIZARD END TO END **AND PRESS CREATE**, then hand the
// readback script the ids of everything the press claimed to make.
//
// ⚠ **THIS IS THE FIRST WALK THAT PRESSES THE BUTTON.** Every earlier
// walkthrough in `10-scripts/` fills the five steps and stops — the nc5
// photograph script says so in its own last line, *"the commit button was NOT
// pressed"*. So nothing until now has verified that this wizard WRITES: not
// that the account appears, not that the money posts, not that the ledger
// balances, not that the rows carry the right tenant. Parts 1 and 2 of this
// script exist to reach the press honestly; the press and what follows it are
// the point.
//
// ⚠ **IT WRITES ROWS. RUN IT AGAINST AN ISOLATED CLONE, NEVER THE DEMO
// DATABASE AND NEVER A SIBLING'S.**
//
//     10-scripts/proof-db.sh clone ncverify
//     # boot the backend against that DATABASE_URL, then:
//     node 10-scripts/po20260929_new_connect_press_create.mjs
//     10-scripts/proof-db.sh drop ncverify
//
// ⚠ The bundle must be built `vite build --mode compose`; a bare build bakes
//   the deployed API host in and sign-in fails with *"That email or password
//   is incorrect."* on correct credentials (`DEF-INF-7802`).
// ⚠ NEVER `playwright install` — chromium is already under `/opt/pw-browsers`.
// ⚠ `fullPage: true` DOES NOT CAPTURE THIS APP. `.app-shell` is
//   `height:100vh; overflow:hidden` and `.view` is the scrolling pane inside
//   it, so `fullPage` silently returns the fold. `shoot()` measures `.view`'s
//   scroll height, grows the viewport and PRINTS every image's dimensions.
//
// ── WHAT IT WRITES OUT ──────────────────────────────────────────────────────
//   <OUT>/00-RESULTS.json   every check, PASS/FAIL/BLOCKED, with its evidence,
//                           plus the commit response and the typed values —
//                           read back by `po20260929_new_connect_readback.py`.
//   <OUT>/*.png             the screenshots each check names.
import { existsSync, mkdirSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = (process.env.NC_BASE ?? "http://127.0.0.1:8080").replace(/\/$/, "");
const TENANT = process.env.NC_TENANT ?? "brazosbend";
const EMAIL = process.env.NC_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.NC_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.NC_OUT ?? "/tmp/nc-press-create";
const UNITS = Number(process.env.NC_UNITS ?? 3);

const STAMP = new Date().toISOString().replace(/[^0-9]/g, "").slice(0, 14);

// ── THE TEN FACTS `DEF-CUS-7863` SAYS NEVER REACH THE SERVER ────────────────
// Typed here as distinctive, greppable values so the readback can look for the
// EXACT string in the database and report arrived / did not arrive, one by one,
// rather than inferring from a payload map.
const TYPED = {
  unit_line: `Bldg A Suite ${STAMP.slice(10)}`,
  lat: "30.245117",
  lng: "-97.769440",
  location_verified: true,
  customer_category: "", // filled from the tenant's own list at run time
  date_of_birth: "1984-03-11",
  comm_paperless: true,
  comm_sms: true,
  co_applicant_name: `Desmond Testcase ${STAMP.slice(10)}`,
  mailing_address: `${STAMP.slice(8)} Mailbox Row`,
  mailing_city: "Houston",
  mailing_state: "TX",
  mailing_zip: "77002",
  account_custom: `CUSTOM-${STAMP.slice(8)}`,
  document_number: `DOC-${STAMP.slice(8)}`,
  owner_name: `Marisol Pressthebutton ${STAMP.slice(8)}`,
  owner_email: `marisol.${STAMP.slice(8)}@example.com`,
  owner_phone: "512-555-0179",
  ssn: "412-88-6630",
  driving_licence: "TX-99441203",
  external_ref: `LEGACY-${STAMP.slice(8)}`,
  premise_address: `${STAMP.slice(8)} Copperleaf Terrace`,
  premise_name: `Copperleaf ${STAMP.slice(8)}`,
  premise_city: "Austin",
  premise_state: "TX",
  premise_zip: "78704",
  // ⚠ **THE PARCEL REF IS OPTIONAL FOR A REASON, AND `NC_PARCEL=""` IS HOW
  // CHECK 23 GETS A HONEST ANSWER.** With one typed, a replayed commit is
  // refused 409 by `premises.external_ref_taken` — a UNIQUENESS CONSTRAINT,
  // not an idempotency key. That is a pass for the wrong reason: it says
  // nothing about what happens on a build with no parcel number, which is
  // every build where the clerk leaves the box empty. Run it BOTH ways.
  parcel: process.env.NC_PARCEL === undefined ? `R-${STAMP.slice(8)}` : process.env.NC_PARCEL,
  payment_amount: "250.00",
  payment_reference: `4471${STAMP.slice(10)}`,
};

const results = [];
const shots = [];
const serverErrors = [];
let commitResponse = null;
let secondCommitResponse = null;

function record(id, label, verdict, evidence = "") {
  results.push({ id, label, verdict, evidence: String(evidence).slice(0, 900) });
  const tag = verdict.padEnd(7);
  console.log(`${tag} ${id.padEnd(7)} ${label}${evidence === "" ? "" : ` — ${evidence}`}`);
}
const pass = (id, l, e) => record(id, l, "PASS", e);
const fail = (id, l, e) => record(id, l, "FAIL", e);
const blocked = (id, l, e) => record(id, l, "BLOCKED", e);
const check = (id, l, ok, e) => (ok ? pass : fail)(id, l, e);
function note(line) {
  console.log(`        · ${line}`);
  results.push({ id: "", label: "note", verdict: "NOTE", evidence: String(line).slice(0, 900) });
}

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  const root = process.env.PLAYWRIGHT_BROWSERS_PATH ?? "/opt/pw-browsers";
  const found = readdirSync(root)
    .filter((n) => n.startsWith("chromium"))
    .flatMap((n) => ["chrome-linux/chrome", "chrome-linux64/chrome"].map((s) => join(root, n, s)))
    .filter(existsSync);
  if (found.length === 0) throw new Error(`no chromium under ${root}`);
  return found[0];
}

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: resolveChromium(), args: ["--no-sandbox"] });
const context = await browser.newContext({ viewport: { width: 1440, height: 1200 } });
const page = await context.newPage();
page.on("response", (r) => {
  if (r.status() >= 500) serverErrors.push(`${r.status()} ${r.url()}`);
});
// The commit's own request body and URL, captured whatever path it takes, so
// the idempotency replay sends the SAME bytes rather than a reconstruction.
let lastCommitRequest = null;
page.on("request", (r) => {
  if (r.method() === "POST" && r.url().includes("/connections/commit")) {
    lastCommitRequest = { url: r.url(), postData: r.postData() };
  }
});

/** The whole step, never the fold. Prints real pixel dimensions. */
async function shoot(name) {
  const width = 1440;
  await page.setViewportSize({ width, height: 1200 });
  await page.waitForTimeout(400);
  const need = await page.evaluate(() => {
    const view = document.querySelector(".view");
    if (view === null) return null;
    return Math.ceil(view.getBoundingClientRect().top + view.scrollHeight + 24);
  });
  const height = Math.min(Math.max(need ?? 1200, 900), 30000);
  await page.setViewportSize({ width, height });
  await page.waitForTimeout(400);
  await page.evaluate(() => {
    const el = document.activeElement;
    if (el instanceof HTMLElement) el.blur();
  });
  const file = join(OUT, `${name}.png`);
  await page.screenshot({ path: file, fullPage: false });
  const bytes = statSync(file).size;
  shots.push({ name, width, height, bytes });
  console.log(`        📷 ${name}.png  ${width}x${height}  ${bytes} bytes`);
  await page.setViewportSize({ width, height: 1200 });
  await page.waitForTimeout(250);
  return { width, height, bytes };
}

const has = async (s) => (await page.locator(s).count()) > 0;
const h1of = async () => (await page.locator("h1").first().innerText().catch(() => "")).trim();
const bodyText = async () => await page.locator("body").innerText();
async function fill(selector, value) {
  if (!(await has(selector))) return false;
  await page.fill(selector, value).catch(() => undefined);
  return true;
}
async function choose(selector, preferred) {
  if (!(await has(selector))) return null;
  const values = await page.$$eval(`${selector} option`, (ns) =>
    ns.filter((o) => !o.disabled && o.value !== "").map((o) => o.value),
  );
  if (values.length === 0) return null;
  const take = preferred !== undefined && values.includes(preferred) ? preferred : values[0];
  await page.selectOption(selector, take);
  return take;
}
/**
 * **TICK A CHECKBOX THE WAY THE KIT LETS YOU.** This component library renders
 * its checkbox `<input>` visually hidden behind a styled box, so Playwright's
 * `.click()` and `.check()` both refuse it as not-visible and the walk then
 * reports `false` for a preference the clerk could tick by hand. Dispatching
 * the click on the input itself is the same event React binds to — the trick
 * `segmented()` below already uses for the radios, applied where it was
 * missing. Returns the state AFTER the tick, read back from the DOM.
 */
async function tick(selector, want = true) {
  const el = await page.$(selector);
  if (el === null) return null;
  const now = await el.evaluate((n) => n.checked);
  if (now !== want) await el.evaluate((n) => n.click());
  await page.waitForTimeout(200);
  return await el.evaluate((n) => n.checked);
}

async function segmented(name, value) {
  const el = await page.$(`input[name="${name}"][value="${value}"]`);
  if (el === null) return false;
  await el.evaluate((n) => n.click());
  return true;
}
const forwardButton = () => page.locator('[data-wizard="actions"] button').last();
async function forward(label) {
  const button = forwardButton();
  const text = (await button.innerText()).trim();
  if (await button.isDisabled()) {
    note(`${label}: the forward button "${text}" is disabled`);
    return false;
  }
  await button.click();
  await page.waitForTimeout(1800);
  return true;
}
const stepNow = async () => {
  const m = (await bodyText()).match(/Step (\d) of 5/);
  return m === null ? null : Number(m[1]);
};

// ════════════════════════════════════════════════════════════════════════════
console.log(`── sign in as ${EMAIL} at ${BASE}/${TENANT}`);
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL(`**/${TENANT}/dashboard`, { timeout: 30000 }).catch(() => undefined);
if (/signin/.test(page.url())) {
  console.error(`sign-in did not leave /signin: ${(await bodyText()).slice(0, 240)}`);
  await page.screenshot({ path: join(OUT, "signin-failed.png") });
  await browser.close();
  process.exit(2);
}

// ════════════════════════════════════════════════════════════════════════════
// PRECONDITION · OPEN A COUNTER, BECAUSE A HAND TENDER NEEDS A TILL
// ════════════════════════════════════════════════════════════════════════════
//
// ⚠ **THIS IS NOT PART OF THE WIZARD AND IT IS NOT A WORKAROUND.** `BR-PAY-1186`
// (PO ruling 2026-09-23 §3.4) refuses a hand-recorded cash, check or money
// order with no open till — *"Start your counter first … It is one press, and
// then you can take the money."* A clerk taking a cheque at the window has
// already made that press. A walk that has not is testing the wizard against a
// precondition it never met, and the honest fix is to meet it.
console.log("\n── precondition · open a counter (BR-PAY-1186)");
// ⚠ `/payments/counter`, SINGULAR — `PAYMENTS_TABS` in `paymentsShared.tsx`.
// A first draft asked for `/payments/counters` and the SPA answered with the
// summary tab, on which there is no Start control: the walk then reported
// "not attempted" and read like a missing button (law 7, looking at the
// wrong thing).
await page.goto(`${BASE}/${TENANT}/payments/counter`, { waitUntil: "networkidle" });
await page.waitForTimeout(2500);
let tillOpened = "not attempted";
// ⚠ **`Start counter →` IS NOT A `<button>`** — B14 rule 4 makes a `Verb →`
// a NAVIGATING control, so it is an anchor in the page head and
// `getByRole("button")` cannot see it. The walk reported "not attempted" over
// a control that is right there.
const startCounter = page.locator("button, a", { hasText: /Start counter/i }).first();
if ((await startCounter.count()) > 0) {
  await startCounter.click().catch(() => undefined);
  await page.waitForTimeout(1200);
  await choose("#service_centre");
  await fill("#opening_float", "200.00");
  // ⚠ `#opened_at` IS LEFT ALONE — the modal defaults it to now and it is a
  // `datetime-local`; overwriting it with a hand-typed string left the form
  // unsubmittable and the walk then reported a counter it had not opened.
  const submit = page.locator('[role="dialog"] button[type="submit"]').first();
  await submit.click().catch(() => undefined);
  await page.waitForTimeout(2500);
  tillOpened = (await bodyText()).replace(/\s+/g, " ").slice(0, 200);
}
note(`precondition · counter: ${tillOpened}`);
await shoot("00-counter-open");

// ════════════════════════════════════════════════════════════════════════════
// STEP 1 · CUSTOMER
// ════════════════════════════════════════════════════════════════════════════
console.log("\n── step 1 · Customer");
await page.goto(`${BASE}/${TENANT}/connections/new`, { waitUntil: "networkidle" });
await page.waitForTimeout(2000);
check("head", "step 1 opens on its drawn H1", (await h1of()) === "Who is asking, and what for?", await h1of());

// ── CHECK 1a · SEARCH AN EXISTING CUSTOMER ─────────────────────────────────
let searchedName = "";
if (await has("#nc_customer_q")) {
  await page.fill("#nc_customer_q", "Ana Alvarez");
  // ⚠ **THE FINDER SEARCHES ON A BUTTON PRESS, NOT ON EVERY KEYSTROKE**
  // (`CustomerFinder`'s own docstring, PO-approved shape of 2026-09-23).
  // A first draft of this walk pressed Enter and reported "no Use button"
  // over a finder that had never been asked anything — law 7's *looking at
  // the wrong thing*.
  const searchBtn = page.locator('[data-step-content="customer-search"] button', {
    hasText: /^Search customer$/,
  });
  if ((await searchBtn.count()) > 0) await searchBtn.first().click();
  else await page.keyboard.press("Enter");
  await page.waitForTimeout(3000);
  const searchPanel = await page
    .locator('[data-step-content="customer-search"]')
    .innerText()
    .catch(() => "");
  // the finder draws a "Use" button per match
  const useButtons = page.locator('[data-step-content="customer-search"] button', { hasText: /^Use$/ });
  const matches = await useButtons.count();
  if (matches > 0) {
    await useButtons.first().click();
    await page.waitForTimeout(1200);
    const after = await page.locator('[data-step-content="customer-search"]').innerText();
    const attached = /Already a customer/i.test(after);
    searchedName = after.replace(/\s+/g, " ").slice(0, 200);
    check("1a", "an EXISTING customer can be searched and attached", attached, searchedName);
    await shoot("01a-existing-customer-attached");
    // ── CHECK 2a · the gov-id panel is GONE over an attached customer ──────
    check(
      "2a",
      "gov-id panel is absent over an attached customer (identity already held)",
      !(await has('[data-gov-id="nc_"]')),
      "no [data-gov-id] while attached",
    );
    // detach so the rest of the walk creates a NEW customer
    const change = page.locator('[data-step-content="customer-search"] button', { hasText: /^Change$/ });
    if ((await change.count()) > 0) {
      await change.first().click();
      await page.waitForTimeout(900);
    }
    await page.fill("#nc_customer_q", "");
  } else {
    fail("1a", "an EXISTING customer can be searched and attached", `no Use button; panel says: ${searchPanel.replace(/\s+/g, " ").slice(0, 250)}`);
  }
} else {
  blocked("1a", "an EXISTING customer can be searched and attached", "#nc_customer_q is not on the screen");
}

// ── CHECK 2 · GOV-ID PANEL, PERSON vs COMPANY ──────────────────────────────
await segmented("nc_party_kind", "person");
await page.waitForTimeout(500);
const personSsn = await has("#nc_ssn");
const personLic = await has("#nc_driving_licence");
const personTax = await has("#nc_tax_id");
await segmented("nc_party_kind", "company");
await page.waitForTimeout(500);
const coSsn = await has("#nc_ssn");
const coTax = await has("#nc_tax_id");
await shoot("02-govid-company");
check(
  "2",
  "gov-id panel is SSN + licence for a Person and Tax ID for a Company",
  personSsn && personLic && !personTax && coTax && !coSsn,
  `person: ssn=${personSsn} licence=${personLic} taxId=${personTax} | company: taxId=${coTax} ssn=${coSsn}`,
);
// back to a person, which is what the rest of the walk commits
await segmented("nc_party_kind", "person");
await page.waitForTimeout(500);
await shoot("02-govid-person");

// ── FILL STEP 1, INCLUDING EVERY ONE OF DEF-CUS-7863's TEN FACTS ───────────
await choose("#nc_owner_kind", "individual_owner");
TYPED.customer_category = (await choose("#nc_owner_category")) ?? "";
await choose("#nc_owner_subcategory", "permanent");
await fill("#nc_owner_name", TYPED.owner_name);
await fill("#nc_owner_dob", TYPED.date_of_birth);
await fill("#nc_owner_email", TYPED.owner_email);
await fill("#nc_owner_phone", TYPED.owner_phone);
await fill("#nc_ssn", TYPED.ssn);
await fill("#nc_driving_licence", TYPED.driving_licence);
// communication preferences
TYPED.comm_paperless = await tick("#nc_paperless", true);
TYPED.comm_sms = await tick("#nc_sms", true);
// co-applicant
const coAdd = page.locator('[data-co-applicant="add"]');
if ((await coAdd.count()) > 0) {
  await coAdd.first().click().catch(() => undefined);
  await page.waitForTimeout(700);
  await choose("#nc_co_owner_kind", "individual_owner");
  await choose("#nc_co_owner_category");
  await segmented("nc_co_party_kind", "person");
  await page.waitForTimeout(300);
  await fill("#nc_co_owner_name", TYPED.co_applicant_name);
  await fill("#nc_co_owner_email", `desmond.${STAMP.slice(8)}@example.com`);
  await fill("#nc_co_owner_phone", "512-555-0180");
  await fill("#nc_co_ssn", "412-88-7741");
}
// mailing address — untick "same as service address" so a real one is typed
await tick("#nc_mail_same", false);
await page.waitForTimeout(500);
await fill("#nc_mail_address", TYPED.mailing_address);
await fill("#nc_mail_city", TYPED.mailing_city);
await fill("#nc_mail_state", TYPED.mailing_state);
await fill("#nc_mail_zip", TYPED.mailing_zip);
// the owner's document, with its number
await choose("#nc-owner-doc-type");
await fill("#nc-owner-doc-number", TYPED.document_number);
await fill("#nc-owner-doc-proves", "Identity");
// account custom data — whatever the tenant defined, if anything
const customInputs = await page
  .locator('[data-step-content="account-details"] input[type="text"], [data-step-content="account-details"] select')
  .count();
if (customInputs > 0) {
  const first = page
    .locator('[data-step-content="account-details"] input[type="text"], [data-step-content="account-details"] select')
    .first();
  const tag = await first.evaluate((n) => n.tagName.toLowerCase());
  if (tag === "input") {
    await first.fill(TYPED.account_custom).catch(() => undefined);
  } else {
    const v = await first.locator("option").nth(1).getAttribute("value").catch(() => null);
    if (v) {
      await first.selectOption(v).catch(() => undefined);
      TYPED.account_custom = v;
    }
  }
} else {
  TYPED.account_custom = null;
  note("step 1 · the tenant defined NO account custom fields, so nothing could be typed into 'Account details' (DEF-CUS-7912's heading-over-nothing)");
}
await fill("#nc_prefix", "NC");
await fill("#nc_external_ref", TYPED.external_ref);
await choose("#nc_mode", "our_crew");
await page.waitForTimeout(500);
// ⚠ **WHAT IS ACTUALLY ON THE SCREEN, READ BACK FROM THE DOM.** Without this
// a value the walk FAILED TO TYPE and a value the SERVER DROPPED look
// identical in the readback, and every "did not arrive" verdict below would
// be unfalsifiable. This is the evidence that makes them mean something.
TYPED.on_screen_step1 = await page.evaluate(() =>
  Object.fromEntries(
    ["nc_owner_name", "nc_owner_dob", "nc_owner_category", "nc_ssn", "nc_driving_licence",
     "nc_paperless", "nc_sms", "nc_mail_same", "nc_mail_address", "nc_mail_city",
     "nc_mail_state", "nc_mail_zip", "nc-owner-doc-number", "nc_co_owner_name", "nc_external_ref"]
      .map((id) => {
        const el = document.getElementById(id);
        return [id, el === null ? "(absent)" : el.type === "checkbox" ? el.checked : el.value];
      }),
  ),
);
console.log("        on screen, step 1:", JSON.stringify(TYPED.on_screen_step1));
await shoot("03-step1-filled");
check("1b", "a NEW customer can be described on step 1", (await page.locator("#nc_owner_name").inputValue()) === TYPED.owner_name, TYPED.owner_name);

if (!(await forward("step 1"))) blocked("flow", "Continue from step 1", "the button was disabled");

// ════════════════════════════════════════════════════════════════════════════
// STEP 2 · PREMISE
// ════════════════════════════════════════════════════════════════════════════
console.log("\n── step 2 · Premise");
await page.waitForTimeout(1200);
check("head2", "step 2 opens on its drawn H1", (await h1of()) === "The premise", await h1of());

// ── CHECK 3a · ADDRESS SEARCH, FOUND ───────────────────────────────────────
await page.fill("#nc_address", "1408 Bluestem");
await page.waitForTimeout(2800);
const foundResults = await page.locator("[data-premises-results] button").count();
const foundText = await page.locator("[data-premises-results]").innerText().catch(() => "");
check("3a", "address search — FOUND state offers the register's rows", foundResults > 0, `${foundResults} result button(s): ${foundText.replace(/\s+/g, " ").slice(0, 200)}`);
await shoot("04-address-found");

// ── CHECK 4 · CITY/STATE/ZIP READ-ONLY OVER A MATCHED PREMISES ─────────────
if (foundResults > 0) {
  await page.locator("[data-premises-results] button").first().click();
  await page.waitForTimeout(1600);
  const picked = await has("[data-premises-picked]");
  const ro = await page.evaluate(() =>
    ["nc_city", "nc_state", "nc_zip"].map((id) => {
      const el = document.getElementById(id);
      return el === null ? `${id}:absent` : `${id}:${el.readOnly ? "readOnly" : "EDITABLE"}`;
    }),
  );
  const values = await page.evaluate(() =>
    ["nc_city", "nc_state", "nc_zip"].map((id) => document.getElementById(id)?.value ?? ""),
  );
  check(
    "4",
    "City/State/ZIP are read-only over a matched premises (hard rule 8)",
    picked && ro.every((r) => r.endsWith(":readOnly")),
    `${ro.join(" · ")} | values ${values.join(" / ")}`,
  );
  await shoot("05-premises-picked-readonly");
  // unpick — the rest of the walk creates a NEW premises so step 12 has one
  if (await has("[data-premises-unpick]")) {
    await page.locator("[data-premises-unpick]").first().click();
    await page.waitForTimeout(900);
  }
} else {
  blocked("4", "City/State/ZIP are read-only over a matched premises", "no premises could be picked — the search found nothing");
}

// ── CHECK 3b · ADDRESS SEARCH, NOT FOUND ───────────────────────────────────
await page.fill("#nc_address", "ZZZQQQ Nowhere At All Street");
await page.waitForTimeout(2800);
const notFoundText = await page.locator("[data-premises-results]").innerText().catch(() => "");
const noneOffered = (await page.locator("[data-premises-results] button").count()) === 0;
check(
  "3b",
  "address search — NOT-FOUND state says so in words",
  noneOffered && /No match/i.test(notFoundText),
  notFoundText.replace(/\s+/g, " ").slice(0, 200) || "(the results area rendered nothing at all)",
);
await shoot("06-address-not-found");

// ── FILL STEP 2, WITH THE FOUR PREMISE FACTS DEF-CUS-7863 NAMES ────────────
await page.fill("#nc_address", TYPED.premise_address);
await page.waitForTimeout(2200);
await fill("#nc_unit", TYPED.unit_line);
await fill("#nc_city", TYPED.premise_city);
await fill("#nc_state", TYPED.premise_state);
await fill("#nc_zip", TYPED.premise_zip);
await fill("#nc_premise_name", TYPED.premise_name);
await choose("#nc_premise_type", "apartment_complex");
if (TYPED.parcel !== "") await fill("#nc_parcel", TYPED.parcel);
await choose("#nc_route");
await fill("#nc_lat", TYPED.lat);
await fill("#nc_lng", TYPED.lng);
TYPED.location_verified = await tick("#nc_location_verified", true);
await choose("#nc_scope", "new_premise");
await page.waitForSelector("#services_available-add", { timeout: 15000 }).catch(() => undefined);
let offered = [];
if (await has("#services_available-add")) {
  offered = await page.$$eval("#services_available-add option", (ns) =>
    ns.map((o) => o.value).filter((v) => v !== ""),
  );
  for (const code of offered) {
    await page.selectOption("#services_available-add", code).catch(() => undefined);
    await page.waitForTimeout(250);
  }
}
TYPED.services = offered;
const planId = await choose("#nc_plan");
TYPED.plan = planId;
await page.waitForTimeout(1500);
TYPED.on_screen_step2 = await page.evaluate(() =>
  Object.fromEntries(
    ["nc_address", "nc_unit", "nc_city", "nc_state", "nc_zip", "nc_premise_name",
     "nc_parcel", "nc_lat", "nc_lng", "nc_location_verified"]
      .map((id) => {
        const el = document.getElementById(id);
        return [id, el === null ? "(absent)" : el.type === "checkbox" ? el.checked : el.value];
      }),
  ),
);
console.log("        on screen, step 2:", JSON.stringify(TYPED.on_screen_step2));
await shoot("07-step2-filled");
if (!(await forward("step 2"))) blocked("flow", "Continue from step 2", "the button was disabled");

// ════════════════════════════════════════════════════════════════════════════
// STEP 3 · UNITS
// ════════════════════════════════════════════════════════════════════════════
console.log("\n── step 3 · Units");
await page.waitForTimeout(1400);
check("head3", "step 3 opens on its drawn H1", (await h1of()) === "The units", await h1of());
await fill("#nc_from", "1");
await fill("#nc_to", String(UNITS));
await page.waitForTimeout(1200);

const serviceCells = () =>
  page.locator('[data-array="units-and-service-points"] [data-cell="service"]').count();

// ── CHECK 5 · ADD ROWS · REMOVE ROWS · APPLY TO ALL ────────────────────────
const beforeAdd = await serviceCells();
await page.locator('[data-array-action="add-row"]').first().click().catch(() => undefined);
await page.waitForTimeout(700);
const afterAdd = await serviceCells();
// ⚠ **`[data-remove-row]`, NOT `[data-array-action="remove-row"]`.** The kit's
// ✕ is `EditableTable`'s own button and carries the row NUMBER as its value;
// there is no `array-action` of that name anywhere in `07-frontend/src`, so a
// walk asking for one reports "0 remove controls" over a table full of them.
const removeButtons = page.locator("[data-remove-row]:not([disabled])");
let afterRemove = afterAdd;
let removeFound = await removeButtons.count();
if (removeFound > 0) {
  await removeButtons.last().click().catch(() => undefined);
  await page.waitForTimeout(700);
  afterRemove = await serviceCells();
}
let appliedTo = null;
if (await has("[data-apply-to-all]")) {
  await choose("#nc_common_occupancy");
  await page.waitForTimeout(400);
  await page.locator("[data-apply-to-all]").first().click().catch(() => undefined);
  await page.waitForTimeout(1000);
  appliedTo = await serviceCells();
}
check(
  "5",
  "step 3 · rows can be added, removed, and Apply-to-all works",
  afterAdd > beforeAdd && removeFound > 0 && afterRemove < afterAdd && appliedTo !== null,
  `rows ${beforeAdd} → +add ${afterAdd} → -remove ${afterRemove}; remove controls ${removeFound}; apply-to-all ${appliedTo === null ? "NOT FOUND" : "pressed"}`,
);
await shoot("08-step3-units");

// ── CHECK 6 · + ADD WORK ORDER OPENS IN PLACE ──────────────────────────────
const dialogsBefore = await page.locator('[role="dialog"]').count();
await page.locator('[data-array-action="add-work-order"]').first().click().catch(() => undefined);
await page.waitForTimeout(900);
const inPlace = await has("#nc_add_order");
const dialogsAfter = await page.locator('[role="dialog"]').count();
check(
  "6",
  '+ Add work order opens IN PLACE — role="dialog" absent afterwards',
  inPlace && dialogsAfter === 0,
  `#nc_add_order present=${inPlace}; [role="dialog"] count ${dialogsBefore} → ${dialogsAfter}`,
);
await shoot("09-step3-add-work-order");

// attach a real work order so step 12 has one to find
let orderPicked = null;
if (await has("#nc_add_order")) {
  await page.fill("#nc_add_order", "");
  await page.waitForTimeout(1600);
  const proposals = page.locator("[data-proposals] button");
  if ((await proposals.count()) > 0) {
    orderPicked = (await proposals.first().innerText()).replace(/\s+/g, " ").slice(0, 120);
    await proposals.first().click().catch(() => undefined);
    await page.waitForTimeout(1200);
  }
}
note(`step 3 · work order attached: ${orderPicked ?? "NONE — the template search offered nothing"}`);
await shoot("10-step3-work-order-attached");
if (!(await forward("step 3"))) blocked("flow", "Continue from step 3", "the button was disabled");

// ════════════════════════════════════════════════════════════════════════════
// STEP 4 · CHARGES
// ════════════════════════════════════════════════════════════════════════════
console.log("\n── step 4 · Charges");
await page.waitForTimeout(1600);
check("head4", "step 4 opens on its drawn H1", (await h1of()) === "Charges", await h1of());
await choose("#nc_quote_payer");
await fill("#nc_quote_due_days", "30");
await fill("#nc_quote_posting_date", "2026-10-01");

// ── CHECK 7 · A SERVER-COMPUTED AMOUNT ─────────────────────────────────────
let chargeCode = null;
let chargeMoney = "";
const addCharge = page.locator('[data-array-action="add-charge"]').first();
if ((await addCharge.count()) > 0 && !(await addCharge.isDisabled())) {
  await addCharge.click().catch(() => undefined);
  await page.waitForTimeout(800);
  const codes = await page
    .$$eval('select[data-cell="charge-0"] option', (ns) =>
      ns.filter((o) => !o.disabled && o.value !== "").map((o) => o.value),
    )
    .catch(() => []);
  if (codes.length > 0) {
    chargeCode = codes[0];
    // watch the quote-preview call, so "server-computed" is evidenced by the
    // response and not by a number that could have been rendered client-side.
    const previewed = page
      .waitForResponse((r) => r.url().includes("/connections/quote-preview") && r.status() < 400, { timeout: 15000 })
      .catch(() => null);
    await page.selectOption('select[data-cell="charge-0"]', chargeCode).catch(() => undefined);
    const resp = await previewed;
    await page.waitForTimeout(2200);
    if (resp !== null) {
      const body = await resp.text().catch(() => "");
      note(`step 4 · POST /connections/quote-preview answered ${resp.status()}: ${body.replace(/\s+/g, " ").slice(0, 400)}`);
      TYPED.quote_preview = body.slice(0, 4000);
    } else {
      note("step 4 · no /connections/quote-preview response was observed");
    }
  }
}
const rowText = await page.locator('[data-array="quote-lines"] tbody tr').first().innerText().catch(() => "");
chargeMoney = (await page.locator("[data-quote-money],[data-charge-total]").allInnerTexts()).join(" | ");
const amountOnRow = rowText.match(/\$[\d,]+\.\d{2}/g) ?? [];
check(
  "7",
  "the charge shows a SERVER-computed amount",
  chargeCode !== null && (amountOnRow.length > 0 || /\$[\d,]+\.\d{2}/.test(chargeMoney)),
  `code ${chargeCode ?? "(none)"}; row "${rowText.replace(/\s+/g, " ").slice(0, 200)}"; totals "${chargeMoney.slice(0, 160)}"; preview seen=${TYPED.quote_preview !== undefined}`,
);
TYPED.charge_code = chargeCode;
TYPED.charge_row = rowText.replace(/\s+/g, " ").slice(0, 300);
await shoot("11-step4-charge-priced");

// ── CHECK 8 · ALL THREE TENDERS, AND THE FIELDS BEFORE A METHOD IS PICKED ──
const beforePick = await page.evaluate(() =>
  ["nc_payment_amount", "nc_payment_reference", "nc_payment_date", "nc_payment_cleared_date"].map((id) => {
    const el = document.getElementById(id);
    return el === null ? `${id}:absent` : `${id}:${el.disabled ? "disabled" : "ENABLED"}`;
  }),
);
const tenderReport = [];
for (const tender of ["cash", "check", "card"]) {
  const got = await choose("#nc_payment_option", tender);
  await page.waitForTimeout(700);
  if (got !== tender) {
    tenderReport.push(`${tender}: NOT OFFERED (got ${got})`);
    continue;
  }
  const state = await page.evaluate(() =>
    ["nc_payment_amount", "nc_payment_reference", "nc_payment_date"].map((id) => {
      const el = document.getElementById(id);
      return el === null ? `${id}:absent` : `${id}:${el.disabled ? "disabled" : "enabled"}`;
    }),
  );
  const label = await page
    .locator('label[for="nc_payment_reference"]')
    .innerText()
    .catch(() => "(no label)");
  tenderReport.push(`${tender}: ${state.join(",")} · reference label "${label.trim()}"`);
  await shoot(`12-tender-${tender}`);
}
const allDisabledBefore = beforePick.every((s) => s.endsWith(":disabled"));
const allEnabledAfter = tenderReport.every((r) => r.includes("NOT OFFERED") === false && !r.includes(":disabled"));
check(
  "8",
  "all three tenders work; the payment fields are inert until a method is picked",
  allDisabledBefore && allEnabledAfter && tenderReport.length === 3 && !tenderReport.some((r) => r.includes("NOT OFFERED")),
  `before any pick: ${beforePick.join(" · ")} || ${tenderReport.join(" || ")}`,
);

// settle on CHECK for the commit
await choose("#nc_payment_option", "check");
await page.waitForTimeout(600);
await fill("#nc_payment_amount", TYPED.payment_amount);
await fill("#nc_payment_reference", TYPED.payment_reference);
await fill("#nc_payment_date", "2026-09-29");
// ⚠ **THE CLEARING DATE DECIDES WHETHER THE LEDGER IS TOUCHED AT ALL**
// (`BR-PAY-021`, `post_payment_cleared`). Blank is lawful and leaves the
// payment `processing` with `journal_entry_id` NULL — correct for a cheque
// handed over today, and a state in which hard rule 5 has nothing to check.
// `NC_CLEARED` fills it so the balanced pair can actually be asked for.
if (process.env.NC_CLEARED) await fill("#nc_payment_cleared_date", process.env.NC_CLEARED);

// ── `DEF-CUS-8020` · STEP 4's BILLING PREFERENCES, TICKED AND TYPED ─────────
//
// ⚠ **THESE FOUR BOXES ARE THE WHOLE OF `DEF-CUS-8020` AND NO WALK HAD EVER
// FILLED THEM.** `step4-charges.png` draws the panel, `commitPlanOf` sends all
// four on the owner block, and `create_master_account` refused every one of
// them — so *Create connection* answered 422 on every press since the panel
// landed, and nothing had ever been created by this wizard. Filling them here
// is what makes check 11 ask the real question rather than a version of it
// with the defect's own trigger left out.
TYPED.autopay = true;
TYPED.tax_exempt = true;
TYPED.tax_exempt_ref = `TX-EX-${STAMP.slice(8)}`;
TYPED.tax_exempt_expires = "2027-12-31";
for (const id of ["#nc_autopay", "#nc_tax_exempt"]) {
  const box = page.locator(id);
  // ⚠ `force: true` — the kit's checkbox hides the real `<input>` under a
  // decorative `[data-checkbox-mark]` span that intercepts the pointer, so an
  // ordinary `.check()` times out on an element that is perfectly clickable
  // for a human. The assertion below reads `isChecked()` afterwards, so the
  // force does not weaken what this proves.
  if ((await box.count()) > 0 && !(await box.isChecked())) await box.check({ force: true });
}
if ((await page.locator("#nc_tax_exempt_ref").count()) > 0) {
  await fill("#nc_tax_exempt_ref", TYPED.tax_exempt_ref);
}
if ((await page.locator("#nc_tax_exempt_expires").count()) > 0) {
  await fill("#nc_tax_exempt_expires", TYPED.tax_exempt_expires);
}
await page.waitForTimeout(600);
await shoot("13-step4-filled");
if (!(await forward("step 4"))) blocked("flow", "Continue from step 4", "the button was disabled");

// ════════════════════════════════════════════════════════════════════════════
// STEP 5 · REVIEW
// ════════════════════════════════════════════════════════════════════════════
console.log("\n── step 5 · Review");
await page.waitForTimeout(1800);
check("head5", "step 5 opens on its drawn H1", (await h1of()) === "What will be created", await h1of());

// ── CHECK 9 · EVERY PANEL EXACTLY ONCE (DEF-CUS-7910) ──────────────────────
const counts = {};
for (const [name, sel] of [
  ["Messages table [data-telling]", "[data-telling]"],
  ["review groups [data-review-group]", "[data-review-group]"],
  ["At-a-glance [data-at-a-glance]", "[data-at-a-glance]"],
  ["What Create makes [data-create-makes]", "[data-create-makes]"],
]) {
  counts[name] = await page.locator(sel).count();
}
counts['heading "Who we are telling"'] = await page.getByText("Who we are telling", { exact: true }).count();
const dupes = Object.entries(counts).filter(([n, c]) => (n.includes("review groups") ? c !== 4 : c !== 1));
check(
  "9",
  "every Review panel appears EXACTLY once (counted, not asserted present)",
  dupes.length === 0,
  Object.entries(counts).map(([n, c]) => `${n} = ${c}`).join(" · "),
);
await shoot("14-step5-review");

// ── CHECK 10 · THE CHARGES TABLE SHOWS EACH AND AMOUNT (DEF-CUS-7911) ──────
let reviewCols = [];
const chargesSummary = page.locator('[data-review-group="charges"] summary');
if ((await chargesSummary.count()) > 0) {
  await chargesSummary.click().catch(() => undefined);
  await page.waitForTimeout(900);
  reviewCols = (await page.locator('[data-array="review-charges"] thead th').allInnerTexts())
    .map((h) => h.trim().toUpperCase())
    .filter((h) => h !== "");
  const openRow = await page
    .locator('[data-array="review-charges"] tbody tr')
    .first()
    .innerText()
    .catch(() => "");
  check(
    "10",
    "the Review charges table shows EACH and AMOUNT",
    reviewCols.includes("EACH") && reviewCols.includes("AMOUNT"),
    `columns: ${reviewCols.join(" · ")} | first row: ${openRow.replace(/\s+/g, " ").slice(0, 160)}`,
  );
  await shoot("15-step5-charges-open");
} else {
  blocked("10", "the Review charges table shows EACH and AMOUNT", "no [data-review-group=charges] summary on the screen");
}

// ── B14 rule 31 / 33 on the last screen before the press ───────────────────
const reviewBody = await bodyText();
const uuidSeen = reviewBody.match(/\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/);
check("r31", "B14 rule 31 — no database id is visible on Review", uuidSeen === null, uuidSeen?.[0] ?? "no uuid on screen");

// ════════════════════════════════════════════════════════════════════════════
// CHECK 11 · PRESS CREATE
// ════════════════════════════════════════════════════════════════════════════
console.log("\n══ PRESSING CREATE ══");

/** Press the last action button and return {status, text, url} of the commit. */
async function pressCreate(tag) {
  // ⚠ **A FAILED COMMIT REPLACES THE ACTION ROW WITH `FailedWithRetry`**
  // (`WizardFrame.tsx`: *"the failed card replaces only the action row"*), so
  // after a refusal there is no `[data-wizard="actions"]` at all and the only
  // way to press again is its *Retry*. A walk that only knows the action row
  // reports "no action button on screen" over a screen holding a live button.
  let button = page.locator('[data-wizard="actions"] button').last();
  if ((await button.count()) === 0) {
    button = page.getByRole("button", { name: /^Retry$/i }).first();
  }
  if ((await button.count()) === 0) return { none: true, why: "no action button and no Retry on screen" };
  const label = (await button.innerText()).trim();
  if (await button.isDisabled()) return { none: true, why: `the button "${label}" is DISABLED`, label };
  const waitCommit = page
    .waitForResponse((r) => r.url().includes("/connections/commit"), { timeout: 60000 })
    .catch(() => null);
  const urlBefore = page.url();
  await button.click();
  const resp = await waitCommit;
  await page.waitForTimeout(4500);
  if (resp === null) return { none: true, why: `pressed "${label}" and no /connections/commit call was made`, label };
  const text = await resp.text().catch(() => "");
  let body = null;
  try {
    body = JSON.parse(text);
  } catch {
    body = { raw: text.slice(0, 3000) };
  }
  await shoot(tag);
  return { label, status: resp.status(), text, body, urlBefore, urlAfter: page.url() };
}

const first = await pressCreate("16-after-create");
if (first.none) {
  fail("11", "PRESS CREATE", first.why);
} else {
  commitResponse = first.body;
  check(
    "11",
    "PRESS CREATE — the commit is accepted and the wizard lands on what it made",
    first.status >= 200 && first.status < 300,
    `button "${first.label}" · POST /connections/commit → ${first.status} · url ${first.urlBefore} → ${first.urlAfter} · body ${first.text.replace(/\s+/g, " ").slice(0, 600)}`,
  );
  note(`after the press the screen says: ${(await bodyText()).replace(/\s+/g, " ").slice(0, 300)}`);
}

// ════════════════════════════════════════════════════════════════════════════
// ⚠⚠ THE HARNESS WORKAROUND IS GONE — `DEF-CUS-8020` IS FIXED (2026-09-29)
// ════════════════════════════════════════════════════════════════════════════
//
// This script used to intercept `POST /connections/commit` in the browser and
// DELETE four keys from the body — `autopay`, `tax_exempt`, `tax_exempt_ref`,
// `tax_exempt_expires` — because `create_master_account` refused all four and
// every real press answered 422. It existed so that steps 12 and 20-25, which
// ask what the commit WRITES, could be asked at all while nothing was ever
// being written. It said out loud that it was not a fix.
//
// ⚠ **IT IS DELETED RATHER THAN LEFT DORMANT.** The block was conditional on
// the 422, so a fixed server would simply never enter it — which is exactly
// how a workaround survives its own cause and quietly re-hides the defect the
// day something re-breaks it. What replaces it is the OPPOSITE check: if the
// four keys are ever refused again, this walk FAILS and names them.
//
// `MASTER_CREATE_FIELDS` now carries the four AND `create_master_account`
// writes them; `tests/test_def_cus_8020_8021_the_create_button.py` is the
// engine-side proof, and this is the browser-side one.
const REFUSED_MASTER_KEYS = ["autopay", "tax_exempt", "tax_exempt_ref", "tax_exempt_expires"];
const refusedAgain =
  first.status === 422 &&
  Array.isArray(first.body?.field_errors) &&
  first.body.field_errors.some((e) => REFUSED_MASTER_KEYS.includes(e.field));
check(
  "11w",
  "DEF-CUS-8020 — the four billing preferences are NOT refused by the master account door",
  !refusedAgain,
  refusedAgain
    ? `the commit was refused naming ${first.body.field_errors.map((e) => e.field).join(", ")} — MASTER_CREATE_FIELDS has lost them again`
    : "no field error names autopay, tax_exempt, tax_exempt_ref or tax_exempt_expires",
);
TYPED.stripped_run = false;

// ════════════════════════════════════════════════════════════════════════════
// CHECK 23 · PRESS CREATE TWICE
// ════════════════════════════════════════════════════════════════════════════
console.log("\n══ PRESSING CREATE A SECOND TIME (hard rule 6) ══");
// The Done screen replaces the wizard, so the second press is the same act a
// clerk performs: go back to the SAME build and press Create again. Anything
// that creates a second account is an idempotency breach.
//
// ⚠ **THE SECOND PRESS IS THE SAME PAYLOAD, SENT AGAIN — WHICH IS WHAT A
// DOUBLE-CLICK, A RETRY AND A BACK-AND-PRESS ALL ARE ON THE WIRE.** After a
// successful commit the wizard leaves Review for its Done screen, so the
// button itself is gone; replaying the identical body through the SAME
// browser session (its cookies, its CSRF token) asks hard rule 6 exactly the
// question it is about. The verdict is decided in the readback by COUNTING
// accounts, never by the second response's status alone.
if (commitResponse !== null && commitResponse.raw === undefined && commitResponse.code === undefined) {
  if (lastCommitRequest === null || !lastCommitRequest.postData) {
    blocked("23", "press Create twice", "the first commit's request body was not captured, so it cannot be replayed");
  } else {
    TYPED.commit_payload_sent = JSON.parse(lastCommitRequest.postData);
    TYPED.commit_url = lastCommitRequest.url;
    secondCommitResponse = await page.evaluate(async ({ url, postData }) => {
      const r = await fetch(url, {
        method: "POST",
        headers: { "content-type": "application/json" },
        credentials: "same-origin",
        body: postData,
      });
      return { status: r.status, text: (await r.text()).slice(0, 1500) };
    }, lastCommitRequest);
    note(`second identical commit → ${secondCommitResponse.status} · ${String(secondCommitResponse.text).replace(/\s+/g, " ").slice(0, 300)}`);
  }
} else {
  blocked("23", "press Create twice", "the first press did not succeed, so a second press proves nothing");
}

// ════════════════════════════════════════════════════════════════════════════
for (const e of serverErrors) fail("5xx", "no 5xx during the run", e);
if (serverErrors.length === 0) pass("5xx", "no 5xx response during the whole walk", "0 responses >= 500");

writeFileSync(
  join(OUT, "00-RESULTS.json"),
  JSON.stringify(
    { stamp: STAMP, base: BASE, tenant: TENANT, typed: TYPED, results, shots, commitResponse, secondCommitResponse, serverErrors },
    null,
    2,
  ) + "\n",
);
const failed = results.filter((r) => r.verdict === "FAIL").length;
const blockedN = results.filter((r) => r.verdict === "BLOCKED").length;
console.log(`\n── ${results.filter((r) => r.verdict !== "NOTE").length} checks · ${failed} FAIL · ${blockedN} BLOCKED`);
console.log(`── ${OUT}/00-RESULTS.json`);
await browser.close();
process.exit(0);
