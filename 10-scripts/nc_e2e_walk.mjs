#!/usr/bin/env node
// ── nc_e2e_walk.mjs ─────────────────────────────────────────────────────────
//
// THE NEW CONNECTION END-TO-END WEB WALK (PO-approved 2026-10-02, decision log
// "THE NEW CONNECTION END-TO-END WEB WALK — APPROVED BY THE PO, AND IT FIXES
// WHAT IT FINDS"). Part 1 of 2: stages 1–8 for ONE building, in a real
// Chromium against a real PostgreSQL 16. Part 2 (`nc_e2e_walk_after.mjs`)
// completes work orders, approves, takes payments and reads the first bill.
//
// One run = one building. `NCW_BUILD` is S1..S8 (the plan's buildings, see
// BUILDINGS below). Writes `<OUT>/nce2e_<S#>_RESULTS.json` (every check, the
// commit response and the ids part 2 needs) and screenshots named
// `nce2e_<S#>_<stage>.png`, each printed with its size so a blank capture is
// visible in the log.
//
// ⚠ IT WRITES ROWS. Run it against a private walk database, never a shared one.
// ⚠ The walk tenant is a utility signed up through the real sign-up
//   (`POST /api/tenants`, all eleven services, defaults + sample data): the
//   demo tenant sells two services and the plan walks eleven.
// ⚠ `fullPage` does not capture this app (`.view` scrolls inside a 100vh
//   shell), so `shoot()` grows the viewport to `.view`'s scroll height.
//
//   NCW_BASE=http://127.0.0.1:8992 NCW_BUILD=S1 NCW_OUT=/tmp/x \
//     node 10-scripts/nc_e2e_walk.mjs
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = (process.env.NCW_BASE ?? "http://127.0.0.1:8992").replace(/\/$/, "");
const TENANT = process.env.NCW_TENANT ?? "lakeside";
const EMAIL = process.env.NCW_EMAIL ?? "lena@lakesidejunction.com";
const PASSWORD = process.env.NCW_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.NCW_OUT ?? "/tmp/nce2e";
const BUILD = process.env.NCW_BUILD ?? "S1";
const STOP_AFTER = Number(process.env.NCW_STOP_AFTER ?? 8);
const STAMP = new Date().toISOString().replace(/[^0-9]/g, "").slice(8, 14);

// ── THE EIGHT BUILDINGS ─────────────────────────────────────────────────────
// Owner identities that later buildings MATCH are fixed strings, so S3/S5/S8
// can type them again (S4's SSN/DL/name+DOB; S1's Tax ID).
const S4_PERSON = { name: "Maya Whitlock", dob: "1979-06-14", ssn: "523-41-7788", dl: "TX-40017788" };
const S1_COMPANY = { name: "Harbor Point Builders LLC", tax: "74-3318620" };
const BUILDINGS = {
  S1: {
    title: "Apartment complex", type: "apartment_complex", party: "company", owner: S1_COMPANY,
    kind: "builder", category: "residential", sub: "permanent", language: "es-MX",
    services: ["electric", "water", "gas", "sewer", "trash", "storm_water", "broadband"],
    units: 3, commonArea: true, unitType: "residential_submetered", occupancy: "VAC",
    sizes: { trash: /96/ }, extraRows: [{ service: /Trash/, asset: /Cart/, size: /64/ }], charges: [/CONN|connect/i], pay: { option: "card", amount: "50.00" },
    customField: "Gate code 4471 — ask for Ruben",
  },
  S2: {
    title: "Commercial building", type: "commercial_building", party: "company",
    owner: { name: "Delgado Retail Holdings Inc", tax: "75-6620194" },
    kind: "landlord", category: "commercial", sub: "permanent", language: "en-US",
    services: ["electric", "water", "fire", "solar", "battery", "thermal_heat"],
    units: 2, commonArea: false, unitType: "commercial", occupancy: "VAC",
    sizes: { water: /1"/, fire: /6"/, battery: /10/, solar: /1 ?kW|P1|1kW/i },
    extraRows: [{ service: /Fire/, asset: /Fire/, size: /^Fire line 2"$/ }, { service: /Fire/, asset: /Fire/, size: /^Fire line 2"$/ }], mailing: { address: "PO Box 2210", city: "Dallas", state: "TX", zip: "75201" },
    charges: [/CONN|connect/i], pay: { option: "card", amount: "0" },
  },
  S3: {
    title: "Mixed-use", type: "mixed_use", party: "person",
    owner: { name: "Tomas Reyes", dob: "1983-11-02", ssn: "611-22-9031", dl: "TX-61122903" },
    matchFirst: { dl: S4_PERSON.dl, expect: "match" },
    kind: "owner_occupier", category: "industrial", sub: "permanent", language: "en-US",
    services: ["electric", "water", "sewer", "trash"], units: 2, commonArea: false,
    unitType: "commercial", unitTypes: ["commercial", "residential"], occupancy: "VAC",
    charges: [/CONN|connect/i], pay: { option: "none" },
  },
  S4: {
    title: "Single-family", type: "single_family", party: "person", owner: S4_PERSON,
    dobChecks: true, coApplicant: { name: "Daniel Whitlock", dob: "1981-02-20", ssn: "523-41-9001" },
    kind: "owner_occupier", category: "residential", sub: "permanent", language: "en-US",
    services: ["water", "sewer", "trash"], units: 1, commonArea: false, unitType: "residential",
    // PO 2026-10-02 item 1: a single-family owner's own account is opened at
    // Create and pays the charges (DEF-CUS-9228), so S4 now carries one.
    occupancy: "OCC-O", sizes: { water: /3\/4/ }, charges: [/CONN|connect/i], pay: { option: "none" },
  },
  S5: {
    title: "Agricultural", type: "single_family", party: "person",
    owner: { name: "Ellen Haverford", dob: "1968-09-30", ssn: "702-55-1846", dl: "TX-70255184" },
    matchFirst: { ssn: S4_PERSON.ssn, expect: "match" }, matchName: { name: S4_PERSON.name, dob: S4_PERSON.dob },
    kind: "owner_occupier", category: "agricultural", sub: "construction_temporary", language: "en-US",
    services: ["electric", "water"], units: 1, commonArea: false, unitType: "residential",
    occupancy: "OCC-O", charges: [/CONN|connect/i], pay: { option: "none" },
  },
  S6: {
    title: "Institutional", type: "commercial_building", party: "company",
    owner: { name: "St. Brendan Academy Trust", tax: "76-1029384" },
    coApplicant: { name: "Margaret Oyelaran", dob: "1975-04-08", ssn: "418-63-2290" },
    kind: "property_manager", category: "institutional", sub: "permanent", language: "fr-CA",
    services: ["electric", "water", "gas", "sewer"], units: 2, commonArea: true, unitType: "commercial",
    occupancy: "VAC", charges: [/CONN|connect/i], pay: { option: "card", amount: "0" },
  },
  S7: {
    title: "Municipal", type: "government_building", party: "company",
    owner: { name: "City of Lakeside Public Works", tax: "77-0001120" },
    kind: "hoa", category: "municipal", sub: "permanent", language: "en-US",
    services: ["electric", "water", "storm_water"], units: 2, commonArea: false, unitType: "commercial",
    occupancy: "VAC", mailing: { address: "100 City Hall Plaza", city: "Lakeside", state: "TX", zip: "78734" },
    charges: [/CONN|connect/i], pay: { option: "none" },
  },
  S8: {
    title: "Repeat owner of S1", type: "apartment_complex", party: "company", owner: S1_COMPANY,
    useMatch: true, kind: "builder", category: "builder_developer", sub: "permanent", language: "en-US",
    services: ["electric", "water"], units: 2, commonArea: false, unitType: "residential_submetered",
    occupancy: "VAC", charges: [/CONN|connect/i], pay: { option: "none" },
  },
};
const B = BUILDINGS[BUILD];
if (B === undefined) throw new Error(`NCW_BUILD must be one of ${Object.keys(BUILDINGS)}`);

const results = [];
const facts = { build: BUILD, title: B.title, stamp: STAMP };
const serverErrors = [];
const record = (verdict, stage, label, evidence = "") => {
  results.push({ verdict, stage, label, evidence: String(evidence).slice(0, 1500) });
  console.log(`${verdict.padEnd(5)} [${stage}] ${label}${evidence === "" ? "" : ` — ${String(evidence).slice(0, 400)}`}`);
};
const check = (stage, label, ok, evidence = "") => record(ok ? "PASS" : "FAIL", stage, label, evidence);
const note = (stage, label, evidence = "") => record("NOTE", stage, label, evidence);

function resolveChromium() {
  const pinned = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
  if (existsSync(pinned)) return pinned;
  const root = "/opt/pw-browsers";
  for (const dir of readdirSync(root)) {
    const c = join(root, dir, "chrome-linux", "chrome");
    if (existsSync(c)) return c;
  }
  throw new Error("no chromium");
}

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: resolveChromium(), args: ["--no-sandbox"] });
const context = await browser.newContext({ viewport: { width: 1440, height: 1200 } });
const page = await context.newPage();
page.on("response", (r) => {
  if (r.status() >= 500) serverErrors.push(`${r.status()} ${r.request().method()} ${r.url()}`);
});
page.on("pageerror", (e) => serverErrors.push(`pageerror ${e.message}`));

async function shoot(stage) {
  await page.setViewportSize({ width: 1440, height: 1200 });
  await page.waitForTimeout(400);
  const need = await page.evaluate(() => {
    const view = document.querySelector(".view");
    return view === null ? null : Math.ceil(view.getBoundingClientRect().top + view.scrollHeight + 24);
  });
  const height = Math.min(Math.max(need ?? 1200, 900), 16000);
  await page.setViewportSize({ width: 1440, height });
  await page.waitForTimeout(400);
  const file = join(OUT, `nce2e_${BUILD}_${stage}.png`);
  await page.screenshot({ path: file });
  const size = statSync(file).size;
  console.log(`      shot ${file} 1440x${height} ${size} bytes`);
  if (size < 20000) record("FAIL", stage, "screenshot looks blank", `${size} bytes`);
  await page.setViewportSize({ width: 1440, height: 1200 });
}
const has = async (s) => (await page.locator(s).count()) > 0;
const bodyText = async () => (await page.locator("body").innerText()).replace(/\s+/g, " ");
async function fill(selector, value) {
  if (!(await has(selector))) return false;
  await page.fill(selector, value).catch(() => undefined);
  return true;
}
async function choose(selector, preferred) {
  if (!(await has(selector))) return null;
  const opts = await page.$$eval(`${selector} option`, (ns) =>
    ns.filter((o) => !o.disabled && o.value !== "").map((o) => ({ v: o.value, t: o.textContent.trim() })),
  );
  if (opts.length === 0) return null;
  let take = opts[0].v;
  if (preferred instanceof RegExp) {
    const hit = opts.find((o) => preferred.test(o.t) || preferred.test(o.v));
    if (hit) take = hit.v;
    else return null;
  } else if (preferred !== undefined) {
    const hit = opts.find((o) => o.v === preferred);
    if (hit) take = hit.v;
    else return null;
  }
  await page.selectOption(selector, take);
  return take;
}
async function chooseIn(locator, preferred) {
  const opts = await locator.evaluate((s) =>
    [...s.options].filter((o) => !o.disabled && o.value !== "").map((o) => ({ v: o.value, t: o.textContent.trim() })),
  );
  const hit = opts.find((o) => preferred.test(o.t) || preferred.test(o.v));
  if (!hit) return { picked: null, offered: opts.map((o) => o.t) };
  await locator.selectOption(hit.v);
  return { picked: hit.t, offered: opts.map((o) => o.t) };
}
async function tick(selector, want = true) {
  const el = await page.$(selector);
  if (el === null) return null;
  if ((await el.evaluate((n) => n.checked)) !== want) await el.evaluate((n) => n.click());
  await page.waitForTimeout(150);
  return el.evaluate((n) => n.checked);
}
async function segmented(name, value) {
  const el = await page.$(`input[name="${name}"][value="${value}"]`);
  if (el === null) return false;
  await el.evaluate((n) => n.click());
  return true;
}
async function forward(stage) {
  const button = page.locator('[data-wizard="actions"] button').last();
  if (await button.isDisabled()) {
    record("FAIL", stage, "forward button disabled", await button.getAttribute("title"));
    return false;
  }
  const before = (await page.locator("h1").first().innerText().catch(() => "")).trim();
  await button.click();
  await page.waitForTimeout(2000);
  const after = (await page.locator("h1").first().innerText().catch(() => "")).trim();
  if (stage !== "1" && after === before) {
    // The press did not move the step: say what the screen shows, so a
    // refusal nobody can see is recorded rather than read as a pass.
    const said = await page.$$eval('[role="alert"], [aria-invalid="true"], .field-error, [data-field-error]', (ns) =>
      ns.map((n) => (n.getAttribute("aria-invalid") === "true" ? `invalid:${n.id || n.getAttribute("name")}` : n.innerText.replace(/\s+/g, " "))).filter(Boolean),
    );
    record("FAIL", stage, "the forward press did not move the step", said.join(" | ") || "nothing on screen says why");
    if (process.env.NCW_DEBUG_DRAFT === "1") {
      // Read the wizard's draft out of React's own state, to say WHY.
      const draft = await page.evaluate(() => {
        const el = document.querySelector('[data-wizard="actions"]');
        const key = el && Object.keys(el).find((k) => k.startsWith("__reactFiber"));
        for (let f = key ? el[key] : null; f; f = f.return) {
          for (let s = f.memoizedState; s; s = s.next) {
            const v = s.memoizedState;
            if (v && typeof v === "object" && "quoteLines" in v && "premise" in v) {
              return JSON.stringify({ owner: v.owner?.name, premise: v.premise, pattern: v.pattern, scope: v.scope });
            }
          }
        }
        return "draft not found";
      });
      note(stage, "draft at the stuck press", draft);
    }
    await shoot(`${stage}_stuck`);
    return false;
  }
  return true;
}
const h1 = async () => (await page.locator("h1").first().innerText().catch(() => "")).trim();
async function matchPanel() {
  await page.waitForTimeout(1800);
  return (await page.locator('[data-step-content="customer-match"]').innerText().catch(() => "")).replace(/\s+/g, " ");
}
const INTERNAL_CODE = /\b(?:DEF|BR|OQ|CR|US|GT)-[A-Z]{0,4}-?\d{2,5}\b|\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-/;

// ── sign in ─────────────────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }).catch(() => undefined);

// ════ STAGE 1 · step 1 ══════════════════════════════════════════════════════
await page.goto(`${BASE}/${TENANT}/connections/new`, { waitUntil: "networkidle" });
await page.waitForTimeout(2000);
check("1", "step 1 opens", (await h1()) === "Who is asking, and what for?", await h1());
const kinds = await page.$$eval("#nc_owner_kind option", (ns) => ns.map((o) => o.textContent.trim()).filter(Boolean));
const cats = await page.$$eval("#nc_owner_category option", (ns) => ns.map((o) => o.textContent.trim()).filter(Boolean));
const subs = await page.$$eval("#nc_owner_subcategory option", (ns) => ns.map((o) => o.textContent.trim()).filter(Boolean));
note("1", "owner types offered", kinds.join(" | "));
note("1", "customer categories offered", cats.join(" | "));
note("1", "sub-categories offered", subs.join(" | "));
facts.kind = await choose("#nc_owner_kind", B.kind);
facts.category = await choose("#nc_owner_category", B.category);
facts.sub = await choose("#nc_owner_subcategory", B.sub);
check("1", `owner type ${B.kind} chosen`, facts.kind === B.kind, String(facts.kind));
check("1", `customer category ${B.category} chosen`, facts.category === B.category, String(facts.category));
check("1", `sub-category ${B.sub} chosen`, facts.sub === B.sub, String(facts.sub));
await segmented("nc_party_kind", B.party);
await page.waitForTimeout(400);
const email = `${BUILD.toLowerCase()}.${STAMP}@example.com`;
await fill("#nc_owner_email", email);
await fill("#nc_owner_phone", "512-555-01" + BUILD.slice(1).padStart(2, "0"));

if (B.party === "company") {
  check("1", "company: Tax ID asked, no SSN box", (await has("#nc_tax_id")) && !(await has("#nc_ssn")));
  note("1", "company: date-of-birth box shown", String(await has("#nc_owner_dob")));
}
if (B.dobChecks) {
  await fill("#nc_owner_name", B.owner.name);
  await fill("#nc_owner_dob", "2031-01-01");
  await page.locator("#nc_owner_email").click();
  await page.waitForTimeout(400);
  const futureErr = await bodyText();
  check("1", "a date of birth in the future is refused", /future|after today|not yet|cannot be/i.test(futureErr.match(/Date of birth.{0,120}/)?.[0] ?? ""), futureErr.match(/Date of birth.{0,120}/)?.[0]);
  await shoot("1a_dob_future");
  await fill("#nc_owner_dob", "2012-05-05");
  await page.locator("#nc_owner_email").click();
  await page.waitForTimeout(400);
  const minorErr = (await bodyText()).match(/Date of birth.{0,120}/)?.[0] ?? "";
  check("1", "an under-18 date of birth is refused", /18|adult|under/i.test(minorErr), minorErr);
  await shoot("1b_dob_under18");
}
// MATCHING: identifiers of an earlier owner first, then the owner's own.
if (B.matchName) {
  await fill("#nc_owner_name", B.matchName.name);
  await fill("#nc_owner_dob", B.matchName.dob);
  const said = await matchPanel();
  check("1", "name + date of birth of an earlier owner is a POSSIBLE match", /possible/i.test(said), said);
  await shoot("1c_possible_match");
  await page.locator('[data-owner-match-action="dismiss"]').first().click().catch(() => undefined);
  await page.waitForTimeout(500);
}
if (B.matchFirst) {
  await fill("#nc_owner_name", B.owner.name);
  if (B.matchFirst.ssn) await fill("#nc_ssn", B.matchFirst.ssn);
  if (B.matchFirst.dl) await fill("#nc_driving_licence", B.matchFirst.dl);
  const said = await matchPanel();
  check("1", `an earlier owner's ${B.matchFirst.ssn ? "SSN" : "licence"} under another name is a MATCH`,
    /match/i.test(said) && !/possible/i.test(said) && /Use this customer/i.test(said), said);
  await shoot("1d_id_match");
  await page.locator('[data-owner-match-action="dismiss"]').first().click().catch(() => undefined);
  await page.waitForTimeout(500);
}
await fill("#nc_owner_name", B.owner.name);
if (B.party === "person") {
  await fill("#nc_owner_dob", B.owner.dob);
  await fill("#nc_ssn", B.owner.ssn);
  await fill("#nc_driving_licence", B.owner.dl);
} else {
  await fill("#nc_tax_id", B.owner.tax);
}
const said = await matchPanel();
note("1", "owner lookup says", said);
if (B.useMatch) {
  check("1", "repeat company by Tax ID is a MATCH", /Use this customer/i.test(said), said);
  await shoot("1e_taxid_match");
  await page.locator('[data-owner-match-action="use"]').first().click().catch(() => undefined);
  await page.waitForTimeout(1000);
  const after = await matchPanel();
  check("1", "Use this customer attaches the earlier customer", /using|attached|release|Not this/i.test(after) || (await has('[data-gov-id="attached"]')), after);
} else {
  check("1", "a new owner is not found", /not found|new customer/i.test(said), said);
}
// MASKING — what is shown for an identifier once typed and left.
await page.locator("#nc_owner_email").click();
const masks = await page.evaluate(() =>
  ["#nc_ssn", "#nc_driving_licence", "#nc_tax_id"].map((s) => {
    const el = document.querySelector(s);
    return el === null ? `${s}:absent` : `${s}:type=${el.type}:value=${el.value}`;
  }),
);
note("1", "identifier boxes after typing (masking)", masks.join(" · "));
if (B.customField) {
  const box = page.locator('[data-step-content="owner"] section input[type="text"]').first();
  const present = (await box.count()) > 0;
  check("1", "the utility's own customer field shows on step 1", present);
  if (present) await box.fill(B.customField);
}
if (B.coApplicant) {
  await page.locator('[data-step-content="co-applicant"] summary, [data-step-content="co-applicant"] button').first().click().catch(() => undefined);
  await page.waitForTimeout(300);
  await page.locator('[data-co-applicant="add"]').click().catch(() => undefined);
  await page.waitForTimeout(400);
  await choose("#nc_co_owner_kind", B.kind);
  await choose("#nc_co_owner_category", B.category);
  await segmented("nc_co_party_kind", "person");
  await fill("#nc_co_owner_name", B.coApplicant.name);
  await fill("#nc_co_owner_dob", B.coApplicant.dob);
  await fill("#nc_co_ssn", B.coApplicant.ssn);
  check("1", "co-applicant form opened and filled", await has("#nc_co_owner_name"));
}
if (B.mailing) {
  await page.locator('[data-step-content="mailing"] summary, [data-step-content="mailing"] button').first().click().catch(() => undefined);
  await page.waitForTimeout(300);
  await tick("#nc_mail_same", false);
  await fill("#nc_mail_address", B.mailing.address);
  await fill("#nc_mail_city", B.mailing.city);
  await fill("#nc_mail_state", B.mailing.state);
  await fill("#nc_mail_zip", B.mailing.zip);
}
facts.language = await choose("#preferred_language", B.language);
note("1", "language chosen", String(facts.language));
await tick("#nc_paperless", BUILD === "S1" || BUILD === "S6");
await tick("#nc_sms", BUILD !== "S7");
await choose("#nc_mode", "our_crew");
await shoot("1_step1");
if (!(await forward("1"))) {
  await shoot("1_refused");
  note("1", "step 1 refusal", await bodyText());
}

// ════ STAGE 2 · step 2 ══════════════════════════════════════════════════════
check("2", "step 2 opens", (await h1()) === "The premise", await h1());
facts.address = `${100 + Number(BUILD.slice(1)) * 11} ${B.title.split(" ")[0]} Lane ${STAMP.slice(2)}`;
await fill("#nc_address", facts.address);
await page.waitForTimeout(1500);
await fill("#nc_city", "Lakeside");
await fill("#nc_state", BUILD === "S6" ? "Texas" : "TX");
await fill("#nc_zip", "78734");
facts.premiseName = `${B.title} ${STAMP}`;
await fill("#nc_premise_name", facts.premiseName);
facts.premiseType = await choose("#nc_premise_type", B.type);
check("2", `premise type ${B.type}`, facts.premiseType === B.type, String(facts.premiseType));
await choose("#nc_route");
await choose("#nc_scope", "new_premise");
await page.waitForTimeout(800);
const stateNote = (await page.locator('[data-step-content="address"]').innerText().catch(() => "")).replace(/\s+/g, " ");
note("2", "address panel facts (City/State check)", stateNote);
// services: pick the building's own, by code, from the add box.
await page.waitForSelector("#services_available-add", { timeout: 15000 }).catch(() => undefined);
for (const code of B.services) {
  const ok = await page.selectOption("#services_available-add", code).then(() => true).catch(() => false);
  if (!ok) note("2", `service ${code} could not be added`, "");
  await page.waitForTimeout(250);
}
await page.waitForTimeout(800);
const plansOffered = await page.$$eval("#nc_plan option", (ns) => ns.map((o) => o.textContent.trim()).filter(Boolean));
note("2", "plans offered", plansOffered.join(" | "));
const want = { residential: /Residential/, commercial: /Commercial/, industrial: /Industrial/ }[B.category];
facts.plan = (await choose("#nc_plan", want ?? /Residential|Commercial|Industrial/)) ?? (await choose("#nc_plan"));
await page.waitForTimeout(2000);
const pricing = (await page.locator('[data-step-content="services-and-plan"]').innerText().catch(() => "")).replace(/\s+/g, " ");
note("2", "services and plan panel", pricing);
check("2", "the pricing table carries a Charge code column", /CHARGE CODE/i.test(pricing));
check("2", "no budget billing control on step 2", !/budget billing/i.test(pricing));
await shoot("2_step2");
if (!(await forward("2"))) {
  await shoot("2_refused");
  note("2", "step 2 refusal", (await bodyText()).slice(0, 1500));
}

// ════ STAGE 3 · step 3 ══════════════════════════════════════════════════════
check("3", "step 3 opens", (await h1()) === "The units", await h1());
await fill("#nc_from", "1");
await fill("#nc_to", String(B.units));
await page.waitForTimeout(800);
if (B.commonArea) await tick("#nc_common_area", true);
await choose("#nc_common_occupancy", B.occupancy);
await choose("#nc_common_unit_type", B.unitType);
const unitTypesOffered = await page.$$eval("#nc_common_unit_type option", (ns) => ns.map((o) => o.textContent.trim()).filter(Boolean));
note("3", "unit types offered", unitTypesOffered.join(" | "));
// the common table: one row per service, asset · size · work order.
// the common table is the step's FIRST table (EditableTable drops data-collection).
const commonRows = page.locator("table").first().locator("tbody tr");
const nCommon = await commonRows.count();
const commonSeen = [];
for (let i = 0; i < nCommon; i += 1) {
  const row = commonRows.nth(i);
  const service = ((await row.locator("td").first().innerText().catch(() => "")) || "").trim();
  const code = B.services.find((c) => service.toLowerCase().replace(/[^a-z]/g, "").startsWith(c.replace(/_/g, "").slice(0, 5)));
  const sizeSel = row.locator('select[data-cell="size"]');
  if (code && B.sizes?.[code] && (await sizeSel.count()) > 0) {
    const r = await chooseIn(sizeSel, B.sizes[code]);
    note("3", `${service} size`, `${r.picked ?? "NOT OFFERED"} (offered: ${r.offered.join(", ")})`);
  }
  const vals = await row.evaluate((tr) =>
    [...tr.querySelectorAll("select")].map((s) => `${s.dataset.cell}=${s.options[s.selectedIndex]?.textContent?.trim() ?? ""}`),
  );
  commonSeen.push(`${service}: ${vals.join(", ") || (await row.innerText()).replace(/\s+/g, " ")}`);
}
note("3", "common selection rows", commonSeen.join(" ‖ "));
if (await has("[data-apply-to-all]")) {
  await page.locator("[data-apply-to-all]").first().click().catch(() => undefined);
  await page.waitForTimeout(1200);
}
// extra rows (S2: two 2" fire lines beside the 6" on the last-touched unit)
for (const extra of B.extraRows ?? []) {
  await page.getByRole("button", { name: "+ Add row" }).click().catch(() => undefined);
  await page.waitForTimeout(600);
  const svc = page.locator('select[data-cell="service"]').last();
  const r1 = await chooseIn(svc, extra.service);
  await page.waitForTimeout(400);
  const row = svc.locator("xpath=ancestor::tr[1]");
  const asset = row.locator('select[data-cell="asset"]');
  const r2 = (await asset.count()) > 0 ? await chooseIn(asset, extra.asset ?? /./) : { picked: "-" };
  await page.waitForTimeout(300);
  const size = row.locator('select[data-cell="size"]');
  const r3 = (await size.count()) > 0 ? await chooseIn(size, extra.size) : { picked: "-", offered: [] };
  note("3", "added row", `${r1.picked} · ${r2.picked} · ${r3.picked} (sizes offered: ${(r3.offered ?? []).join(", ")})`);
}
const tilesTxt = (await bodyText()).match(/SERVICES HERE.*?(?=Common selection)/i)?.[0] ?? "";
const tilesAll = [tilesTxt];
note("3", "step 3 tiles", tilesTxt);
facts.step3Tiles = tilesAll;
await shoot("3_step3");
if (!(await forward("3"))) {
  await shoot("3_refused");
  note("3", "step 3 refusal", (await bodyText()).slice(0, 1500));
}

// ════ STAGE 4 · step 4 ══════════════════════════════════════════════════════
check("4", "step 4 opens", (await h1()) === "Charges", await h1());
const addCharge = page.locator('[data-array-action="add-charge"]').first();
facts.charges = [];
for (const re of B.charges) {
  if ((await addCharge.count()) === 0 || (await addCharge.isDisabled())) {
    note("4", "+ Charge unavailable", await addCharge.getAttribute("title").catch(() => ""));
    break;
  }
  await addCharge.click();
  await page.waitForTimeout(800);
  const sel = page.locator('select[data-cell^="charge"]').last();
  const r = await chooseIn(sel, re);
  note("4", "charge picked", `${r.picked ?? "none matched"} (offered: ${r.offered.slice(0, 30).join(", ")})`);
  if (r.picked === null) await chooseIn(sel, /./);
  facts.charges.push(r.picked);
  await page.waitForTimeout(2500);
}
if (B.charges.length === 0) {
  // A building with no charge picked: show what step 4 says about it.
  const refusal = (await page.locator("[data-no-billable-charge]").innerText().catch(() => "")).replace(/\s+/g, " ");
  note("4", "no master account: what step 4 says about charges", refusal || (await bodyText()).match(/master account.{0,80}/i)?.[0] || "");
}
facts.payer = await choose("#nc_quote_payer");
facts.terms = await choose("#nc_quote_due_days", "30");
const totals = (await page.locator("[data-charge-totals]").innerText().catch(() => "")).replace(/\s+/g, " ");
note("4", "charge totals", totals);
facts.chargeTotal = totals;
if (B.pay.option === "card") {
  if ((await choose("#nc_payment_option", "card")) === "card") {
    await page.waitForTimeout(500);
    // amount "0" = pay the whole total (the EXACT case); else a PART payment.
    let amount = B.pay.amount;
    if (amount === "0") {
      const m = totals.match(/Total \$?([\d,]+\.\d\d)/);
      amount = m ? m[1].replace(/,/g, "") : "1.00";
    }
    facts.paidAtCreate = amount;
    await fill("#nc_payment_amount", amount);
    await fill("#nc_payment_reference", `AUTH-${BUILD}-${STAMP}`);
    await fill("#nc_payment_date", "2026-10-02");
    // S1 leaves the clearing date empty (the money has not arrived: the
    // payment is recorded, meets no bill); the others clear the same day.
    if (BUILD !== "S1") await fill("#nc_payment_cleared_date", "2026-10-02");
    note("4", "card payment typed", `${amount} ref AUTH-${BUILD}-${STAMP}`);
  } else note("4", "card option not offered", "");
} else {
  await choose("#nc_payment_option", "none").catch(() => undefined);
}
await page.waitForTimeout(800);
const termsTxt = (await page.locator("[data-charge-totals]").innerText().catch(() => "")).replace(/\s+/g, " ");
note("4", "totals after payment", termsTxt);
await shoot("4_step4");
if (!(await forward("4"))) {
  await shoot("4_refused");
  note("4", "step 4 refusal", (await bodyText()).slice(0, 1500));
}

// ════ STAGE 5 · step 5 ══════════════════════════════════════════════════════
check("5", "step 5 opens", (await h1()) === "What will be created", await h1());
await page.waitForTimeout(1500);
const glance = await page.$$eval("[data-glance-cell]", (ns) => ns.map((n) => n.innerText.replace(/\s+/g, " ")));
note("5", "at a glance", glance.join(" · "));
facts.glance = glance;
const messages = await page.$$eval("[data-template-row], [data-message-state]", (ns) =>
  ns.map((n) => (n.closest("tr") ?? n).innerText.replace(/\s+/g, " ")),
);
const msgRows = await page.$$eval("table", (ts) => {
  const t = ts.find((x) => /COMMUNICATION/i.test(x.innerText));
  return t ? [...t.querySelectorAll("tbody tr")].map((r) => r.innerText.replace(/\s+/g, " ")) : [];
});
note("5", "messages table", msgRows.join(" ‖ ") || messages.join(" ‖ "));
facts.step5Messages = msgRows;
const makes = await page.$$eval("[data-create-makes] tbody tr, [data-creates]", (ns) =>
  ns.map((n) => n.innerText.replace(/\s+/g, " ")),
);
note("5", "What Create makes", makes.join(" ‖ "));
facts.createMakes = makes;
const review = await bodyText();
check("5", "no database id or internal code on review", !INTERNAL_CODE.test(review), review.match(INTERNAL_CODE)?.[0]);
check("5", "language shown on review", /Preferred language/i.test(review), review.match(/Preferred language.{0,40}/)?.[0]);
await shoot("5_step5");
// NCW_NO_CREATE=1 — a re-walk of steps 1–5 after a fix, without making a build.
if (process.env.NCW_NO_CREATE === "1") {
  for (const e of serverErrors) record("FAIL", "any", "5xx or page error during the walk", e);
  writeFileSync(join(OUT, `nce2e_${BUILD}_REWALK.json`), JSON.stringify({ facts, results, serverErrors }, null, 2));
  await browser.close();
  console.log(`── ${BUILD} re-walk (no Create): ${results.length} checks, ${results.filter((r) => r.verdict === "FAIL").length} FAIL`);
  process.exit(0);
}

// ════ STAGE 6 · Create → Done ═══════════════════════════════════════════════
const button = page.locator('[data-wizard="actions"] button').last();
const wait = page.waitForResponse((r) => r.url().includes("/connections/commit"), { timeout: 120000 }).catch(() => null);
await button.click();
const resp = await wait;
await page.waitForTimeout(4000);
const status = resp === null ? "none" : resp.status();
let commit = null;
try {
  commit = resp === null ? null : await resp.json();
} catch {
  commit = null;
}
facts.commit = commit;
check("6", "Create accepted", typeof status === "number" && status < 300, `${status} ${JSON.stringify(commit).slice(0, 600)}`);
const done = await bodyText();
check("6", "Done screen shows", await has("[data-commit-done]"), done.slice(0, 300));
check("6", "Done screen carries no internal code or database id", !INTERNAL_CODE.test(done), done.match(INTERNAL_CODE)?.[0]);
let openLink = null;
const openBtn = page.getByRole("button", { name: /Open the connection/ }).or(page.getByRole("link", { name: /Open the connection/ }));
await shoot("6_done");
if ((await openBtn.count()) > 0) {
  await openBtn.first().click();
  await page.waitForTimeout(2500);
  openLink = page.url();
}
check("6", "Done screen opens the request", openLink !== null && /\/connections\//.test(openLink), String(openLink));
note("6", "Done screen text", done.replace(/^.*?System Admin/i, "").slice(0, 900));
facts.connectionId = openLink?.match(/connections\/([0-9a-f-]{36})/)?.[1] ?? commit?.connection_id ?? commit?.id ?? null;

// ════ STAGE 7 · every tab of the request ════════════════════════════════════
if (facts.connectionId !== null && STOP_AFTER >= 7) {
  await page.goto(`${BASE}/${TENANT}/connections/${facts.connectionId}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2500);
  const tabs = await page.$$eval('[role="tab"]', (ns) => ns.map((n) => ({ t: n.innerText.trim(), id: n.id || n.getAttribute("aria-controls") || "" })));
  note("7", "tabs on the request", tabs.map((t) => t.t).join(" | "));
  facts.tabs = tabs.map((t) => t.t);
  const header = (await page.locator("[data-build-detail]").first().innerText().catch(() => "")).replace(/\s+/g, " ").slice(0, 400);
  note("7", "request header", header);
  for (let i = 0; i < tabs.length; i += 1) {
    const tab = page.locator('[role="tab"]').nth(i);
    await tab.click().catch(() => undefined);
    await page.waitForTimeout(1800);
    const name = tabs[i].t.replace(/[^A-Za-z]+/g, "").toLowerCase() || `tab${i}`;
    const text = (await page.locator(".view").innerText().catch(() => "")).replace(/\s+/g, " ");
    check("7", `tab ${tabs[i].t} renders without an internal code`, !INTERNAL_CODE.test(text), text.match(INTERNAL_CODE)?.[0]);
    facts[`tab_${name}`] = text.slice(0, 3000);
    await shoot(`7_tab_${name}`);
  }
}

for (const e of serverErrors) record("FAIL", "any", "5xx or page error during the walk", e);
writeFileSync(join(OUT, `nce2e_${BUILD}_RESULTS.json`), JSON.stringify({ facts, results, serverErrors }, null, 2));
await browser.close();
const failed = results.filter((r) => r.verdict === "FAIL").length;
console.log(`── ${BUILD}: ${results.length} checks, ${failed} FAIL — connection ${facts.connectionId}`);
process.exit(0);
