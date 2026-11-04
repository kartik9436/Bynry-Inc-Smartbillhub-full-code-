#!/usr/bin/env node
// ── po20260929_new_connect_clerk_errors.mjs ────────────────────────────────
//
// **PART 2 — WHAT A CLERK DOES WRONG.** Checks 13-19 of the 2026-09-29 New
// Connect verification: empty required fields on every step, walking back and
// forth, parking and resuming, old `?step=` links, and the three rules that
// refuse a build (a service the street cannot deliver, sewer without water,
// and a premises that already takes the service).
//
// ⚠ **IT WRITES ALMOST NOTHING** — only a parked draft for check 15. Run it
// against the same ISOLATED CLONE as the press-Create walk, never the demo
// database.
//
// ⚠ Bundle must be `vite build --mode compose` (`DEF-INF-7802`). Never
//   `playwright install`. `fullPage: true` does not capture this frame.
import { existsSync, mkdirSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = (process.env.NC_BASE ?? "http://127.0.0.1:8080").replace(/\/$/, "");
const TENANT = process.env.NC_TENANT ?? "brazosbend";
const EMAIL = process.env.NC_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.NC_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.NC_OUT ?? "/tmp/nc-clerk-errors";
const STAMP = new Date().toISOString().replace(/[^0-9]/g, "").slice(0, 14);

const results = [];
function record(id, label, verdict, evidence = "") {
  results.push({ id, label, verdict, evidence: String(evidence).slice(0, 900) });
  console.log(`${verdict.padEnd(7)} ${id.padEnd(5)} ${label}${evidence === "" ? "" : ` — ${evidence}`}`);
}
const check = (id, l, ok, e) => record(id, l, ok ? "PASS" : "FAIL", e);
const blocked = (id, l, e) => record(id, l, "BLOCKED", e);
function note(line) {
  console.log(`        · ${line}`);
  results.push({ id: "", label: "note", verdict: "NOTE", evidence: String(line).slice(0, 900) });
}

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  const root = process.env.PLAYWRIGHT_BROWSERS_PATH ?? "/opt/pw-browsers";
  return readdirSync(root)
    .filter((n) => n.startsWith("chromium"))
    .flatMap((n) => ["chrome-linux/chrome", "chrome-linux64/chrome"].map((s) => join(root, n, s)))
    .filter(existsSync)[0];
}

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: resolveChromium(), args: ["--no-sandbox"] });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 1200 } })).newPage();

async function shoot(name) {
  const need = await page.evaluate(() => {
    const v = document.querySelector(".view");
    return v === null ? null : Math.ceil(v.getBoundingClientRect().top + v.scrollHeight + 24);
  });
  const height = Math.min(Math.max(need ?? 1200, 900), 30000);
  await page.setViewportSize({ width: 1440, height });
  await page.waitForTimeout(350);
  const file = join(OUT, `${name}.png`);
  await page.screenshot({ path: file });
  console.log(`        📷 ${name}.png  1440x${height}  ${statSync(file).size} bytes`);
  await page.setViewportSize({ width: 1440, height: 1200 });
}

const has = async (s) => (await page.locator(s).count()) > 0;
const bodyText = async () => await page.locator("body").innerText();
const h1of = async () => (await page.locator("h1").first().innerText().catch(() => "")).trim();
async function fill(s, v) {
  if (!(await has(s))) return false;
  await page.fill(s, v).catch(() => undefined);
  return true;
}
async function choose(s, preferred) {
  if (!(await has(s))) return null;
  const values = await page.$$eval(`${s} option`, (ns) =>
    ns.filter((o) => !o.disabled && o.value !== "").map((o) => o.value),
  );
  if (values.length === 0) return null;
  const take = preferred !== undefined && values.includes(preferred) ? preferred : values[0];
  await page.selectOption(s, take);
  return take;
}
async function segmented(name, value) {
  const el = await page.$(`input[name="${name}"][value="${value}"]`);
  if (el === null) return false;
  await el.evaluate((n) => n.click());
  return true;
}
const forwardButton = () => page.locator('[data-wizard="actions"] button').last();
/** `true` when the forward button is unusable OR ABSENT — a failed commit
 *  replaces the whole action row with `FailedWithRetry`, and `isDisabled()`
 *  on a locator matching nothing waits 30s and throws rather than answering. */
async function forwardBlocked() {
  if ((await page.locator('[data-wizard="actions"] button').count()) === 0) return true;
  return await forwardButton().isDisabled();
}
const backButton = () =>
  page.locator('[data-wizard="actions"] button', { hasText: /^(Back|← Back)$/ }).first();
const stepNow = async () => {
  const m = (await bodyText()).match(/Step (\d) of (\d)/);
  return m === null ? null : Number(m[1]);
};
/** Everything the screen is currently refusing, in the clerk's own words. */
const refusals = async () => {
  const said = await page
    .locator('[data-wizard="blocked"], [data-refusal], [role="alert"], .text-danger-500')
    .allInnerTexts();
  return said.map((s) => s.replace(/\s+/g, " ").trim()).filter(Boolean);
};

// ── sign in ────────────────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL(`**/${TENANT}/dashboard`, { timeout: 30000 }).catch(() => undefined);

// ════════════════════════════════════════════════════════════════════════════
// CHECK 16 · OLD ?step=6 / 7 / 8 LINKS
// ════════════════════════════════════════════════════════════════════════════
//
// ⚠ **A NAIVE REMAP ONCE WALLED THE WIZARD** — Continue did nothing, forever,
// with no error — so this asks TWO questions, not one: where does the link
// LAND, and does Continue still MOVE from there. A check that only asserts the
// landing step is exactly the one that would have passed over the wall.
console.log("\n── check 16 · old ?step= links");
const remaps = [];
for (const step of [6, 7, 8]) {
  await page.goto(`${BASE}/${TENANT}/connections/new?step=${step}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2200);
  const landed = await stepNow();
  const heading = await h1of();
  const button = forwardButton();
  const label = (await button.count()) > 0 ? (await button.innerText()).trim() : "(no button)";
  const disabled = (await button.count()) > 0 ? await button.isDisabled() : null;
  // press it and see whether ANYTHING happens — a wall is a live button that
  // moves nothing and says nothing.
  let moved = null;
  let said = [];
  if ((await button.count()) > 0 && disabled === false) {
    await button.click().catch(() => undefined);
    await page.waitForTimeout(1500);
    moved = await stepNow();
    said = await refusals();
  }
  remaps.push({ step, landed, heading, label, disabled, afterPress: moved, said });
  await shoot(`16-step${step}`);
}
const walled = remaps.filter(
  (r) => r.disabled === false && r.afterPress === r.landed && r.said.length === 0,
);
check(
  "16",
  "old ?step=6/7/8 links land somewhere real and Continue is not walled",
  remaps.every((r) => r.landed !== null && r.landed >= 1 && r.landed <= 5) && walled.length === 0,
  remaps
    .map(
      (r) =>
        `?step=${r.step} → step ${r.landed} "${r.heading}" · forward "${r.label}" disabled=${r.disabled}` +
        (r.afterPress === null ? "" : ` · after pressing: step ${r.afterPress}${r.said.length ? ` saying "${r.said.join(" | ").slice(0, 120)}"` : " AND SAID NOTHING"}`),
    )
    .join(" || "),
);

// ════════════════════════════════════════════════════════════════════════════
// CHECK 13 · CONTINUE WITH REQUIRED FIELDS EMPTY, ON EVERY STEP
// ════════════════════════════════════════════════════════════════════════════
//
// ⚠ **THE QUESTION IS NOT "IS IT REFUSED", IT IS "DOES THE REFUSAL NAME THE
// STEP THAT HOLDS THE FIELD".** `DEF-MET-6110`/`6111` are exactly the failure
// where a rule refusal lands on the wrong step, so each refusal is captured
// verbatim and read against the step the clerk is standing on.
console.log("\n── check 13 · Continue with required fields empty");
//
// ⚠ **A FIRST DRAFT OF THIS CHECK ONLY EVER TESTED STEP 1**, because a wizard
// that correctly refuses an empty step 1 never lets the walk reach step 2 —
// so the loop reported *"step 2: never reached"* and read like a product
// failure. To ask the question of step N the walk has to FILL steps 1..N-1
// and then press Continue on N with nothing in it. That is what this does,
// and it is the difference between testing five steps and testing one.
const fillers = {
  1: async () => {
    await choose("#nc_owner_kind", "individual_owner");
    await choose("#nc_owner_category");
    await choose("#nc_owner_subcategory", "permanent");
    await segmented("nc_party_kind", "person");
    await page.waitForTimeout(250);
    await fill("#nc_owner_name", `Emptystep ${STAMP.slice(8)}`);
    await fill("#nc_owner_email", `empty.${STAMP.slice(8)}@example.com`);
    await fill("#nc_ssn", "412-88-5500");
    await choose("#nc_mode", "our_crew");
  },
  2: async () => {
    await fill("#nc_address", `${STAMP.slice(8)} Emptystep Lane`);
    await page.waitForTimeout(2000);
    await fill("#nc_city", "Austin");
    await fill("#nc_state", "TX");
    await fill("#nc_zip", "78704");
    await choose("#nc_premise_type", "apartment_complex");
    await choose("#nc_scope", "new_premise");
    await page.waitForSelector("#services_available-add", { timeout: 12000 }).catch(() => undefined);
    if (await has("#services_available-add")) {
      const offered = await page.$$eval("#services_available-add option", (ns) =>
        ns.map((o) => o.value).filter((v) => v !== ""));
      for (const code of offered) {
        await page.selectOption("#services_available-add", code).catch(() => undefined);
        await page.waitForTimeout(220);
      }
    }
    await choose("#nc_plan");
  },
  3: async () => {
    await fill("#nc_from", "1");
    await fill("#nc_to", "2");
    await page.waitForTimeout(1100);
    if (await has("[data-apply-to-all]")) {
      await page.locator("[data-apply-to-all]").first().click().catch(() => undefined);
      await page.waitForTimeout(900);
    }
  },
  4: async () => {
    await choose("#nc_quote_payer");
    await fill("#nc_quote_due_days", "30");
  },
};
const emptyStepReports = [];
for (let target = 1; target <= 5; target += 1) {
  await page.goto(`${BASE}/${TENANT}/connections/new`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2200);
  let reached = true;
  for (let prior = 1; prior < target; prior += 1) {
    await fillers[prior]();
    await page.waitForTimeout(700);
    if (await forwardBlocked()) { reached = false; break; }
    await forwardButton().click();
    await page.waitForTimeout(1700);
  }
  const at = await stepNow();
  if (!reached || at !== target) {
    emptyStepReports.push({ step: target, reached: false, at });
    continue;
  }
  const disabled = await forwardBlocked();
  const label = disabled && (await page.locator('[data-wizard="actions"] button').count()) === 0
    ? "(no action row)"
    : (await forwardButton().innerText()).trim();
  if (!disabled) await forwardButton().click().catch(() => undefined);
  await page.waitForTimeout(1600);
  const after = await stepNow();
  const said = await refusals();
  emptyStepReports.push({ step: target, reached: true, label, disabled, after, said });
  await shoot(`13-empty-step${target}`);
}
// Step 5 is the COMMIT step: "empty" there means the steps behind it are
// empty, and the honest question is whether the refusal names the step that
// HOLDS the field. Every other step must simply not advance.
const held = emptyStepReports.filter((r) => r.reached && r.step < 5)
  .every((r) => r.disabled === true || r.after === r.step);
const spoke = emptyStepReports.filter((r) => r.reached && r.step < 5)
  .every((r) => r.disabled === true || r.said.length > 0);
const unreached = emptyStepReports.filter((r) => !r.reached);
check(
  "13",
  "Continue on an EMPTY step is refused on the step that holds the field, in words",
  held && spoke && unreached.length === 0,
  emptyStepReports
    .map((r) =>
      r.reached
        ? `step ${r.step}: "${r.label}" disabled=${r.disabled} -> landed on step ${r.after}` +
          (r.said.length ? ` saying "${r.said.join(" | ").slice(0, 140)}"` : " WITH NO SENTENCE")
        : `step ${r.step}: NOT REACHED (the walk stopped at ${r.at})`)
    .join(" || "),
);

// ════════════════════════════════════════════════════════════════════════════
// CHECK 14 · BACK AND FORTH ACROSS ALL FIVE STEPS
// ════════════════════════════════════════════════════════════════════════════
console.log("\n── check 14 · back and forth");
await page.goto(`${BASE}/${TENANT}/connections/new`, { waitUntil: "networkidle" });
await page.waitForTimeout(2200);

const TYPED = {
  owner: `Backandforth ${STAMP.slice(8)}`,
  email: `bf.${STAMP.slice(8)}@example.com`,
  phone: "512-555-0142",
  ssn: "412-88-9001",
  dob: "1979-07-04",
  address: `${STAMP.slice(8)} Reversal Road`,
  city: "Austin",
  zip: "78704",
  premiseName: `Reversal ${STAMP.slice(8)}`,
  unitLine: `Wing B ${STAMP.slice(10)}`,
};
await choose("#nc_owner_kind", "individual_owner");
await choose("#nc_owner_category");
await choose("#nc_owner_subcategory", "permanent");
await segmented("nc_party_kind", "person");
await page.waitForTimeout(300);
await fill("#nc_owner_name", TYPED.owner);
await fill("#nc_owner_email", TYPED.email);
await fill("#nc_owner_phone", TYPED.phone);
await fill("#nc_ssn", TYPED.ssn);
await fill("#nc_owner_dob", TYPED.dob);
await choose("#nc_mode", "our_crew");
await page.waitForTimeout(400);
await forwardButton().click();
await page.waitForTimeout(1600);

await fill("#nc_address", TYPED.address);
await page.waitForTimeout(2000);
await fill("#nc_unit", TYPED.unitLine);
await fill("#nc_city", TYPED.city);
await fill("#nc_state", "TX");
await fill("#nc_zip", TYPED.zip);
await fill("#nc_premise_name", TYPED.premiseName);
await choose("#nc_premise_type", "apartment_complex");
await choose("#nc_scope", "new_premise");
await page.waitForSelector("#services_available-add", { timeout: 12000 }).catch(() => undefined);
if (await has("#services_available-add")) {
  const offered = await page.$$eval("#services_available-add option", (ns) =>
    ns.map((o) => o.value).filter((v) => v !== ""),
  );
  for (const code of offered) {
    await page.selectOption("#services_available-add", code).catch(() => undefined);
    await page.waitForTimeout(220);
  }
}
await choose("#nc_plan");
await page.waitForTimeout(1200);
await forwardButton().click();
await page.waitForTimeout(1700);

await fill("#nc_from", "1");
await fill("#nc_to", "2");
await page.waitForTimeout(1200);
await forwardButton().click();
await page.waitForTimeout(1700);
const reachedCharges = await stepNow();
await fill("#nc_quote_due_days", "45");
await page.waitForTimeout(400);

// walk BACK to step 1, then FORWARD again to step 4, reading every value
async function readAll() {
  return await page.evaluate(() =>
    Object.fromEntries(
      [
        "nc_owner_name", "nc_owner_email", "nc_owner_phone", "nc_ssn", "nc_owner_dob",
        "nc_address", "nc_unit", "nc_city", "nc_state", "nc_zip", "nc_premise_name",
        "nc_from", "nc_to", "nc_quote_due_days",
      ]
        .map((id) => {
          const el = document.getElementById(id);
          return el === null ? null : [id, el.type === "checkbox" ? el.checked : el.value];
        })
        .filter(Boolean),
    ),
  );
}
const seen = {};
for (let i = 0; i < 3; i += 1) {
  Object.assign(seen, await readAll());
  const back = backButton();
  if ((await back.count()) === 0 || (await back.isDisabled())) break;
  await back.click();
  await page.waitForTimeout(1400);
}
const atStep1 = await stepNow();
Object.assign(seen, await readAll());
await shoot("14-walked-back");
for (let i = 0; i < 3; i += 1) {
  if (await forwardBlocked()) break;
  await forwardButton().click();
  await page.waitForTimeout(1500);
  Object.assign(seen, await readAll());
}
const atStepAgain = await stepNow();
await shoot("14-walked-forward-again");
const lost = Object.entries({
  nc_owner_name: TYPED.owner,
  nc_owner_email: TYPED.email,
  nc_owner_phone: TYPED.phone,
  nc_ssn: TYPED.ssn,
  nc_owner_dob: TYPED.dob,
  nc_address: TYPED.address,
  nc_unit: TYPED.unitLine,
  nc_city: TYPED.city,
  nc_zip: TYPED.zip,
  nc_premise_name: TYPED.premiseName,
  nc_from: "1",
  nc_to: "2",
  nc_quote_due_days: "45",
}).filter(([id, want]) => seen[id] !== undefined && String(seen[id]) !== String(want));
check(
  "14",
  "back and forth across all five steps loses nothing",
  lost.length === 0,
  `walked back to step ${atStep1} and forward to step ${atStepAgain} (charges was reached at ${reachedCharges}) · ` +
    (lost.length === 0
      ? `all ${Object.keys(seen).length} values re-read unchanged`
      : `LOST: ${lost.map(([id, want]) => `${id} wanted "${want}" saw "${seen[id]}"`).join("; ")}`),
);

// ════════════════════════════════════════════════════════════════════════════
// CHECK 15 · PARK A DRAFT, LEAVE, RESUME
// ════════════════════════════════════════════════════════════════════════════
console.log("\n── check 15 · park, leave, resume");
const parkedAt = await stepNow();
let parkRef = null;
const parkToggle = page.locator('[data-wizard="exit"] button', { hasText: /Park/i }).first();
if ((await parkToggle.count()) > 0 && !(await parkToggle.isDisabled())) {
  await parkToggle.click().catch(() => undefined);
  await page.waitForTimeout(900);
  await choose("#wizard_park_reason", "materials");
  const commit = page
    .locator("button", { hasText: /^(Park|Park it|Park this|Save)$/i })
    .last();
  await commit.click().catch(() => undefined);
  await page.waitForTimeout(2600);
  const after = (await bodyText()).replace(/\s+/g, " ");
  parkRef = (after.match(/\b(NC|PRK|WIZ)[-A-Z0-9]{4,}\b/) ?? [])[0] ?? null;
  note(`after parking, the screen says: ${after.slice(0, 250)}`);
  await shoot("15-parked");
} else {
  note("the Park control was absent or disabled on this step");
}

// leave for a completely different screen, then come back the way a clerk does
await page.goto(`${BASE}/${TENANT}/dashboard`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
// ⚠ `/accounts?tab=new-connects`, NOT `/connections`. `BuildDetailPage`
// exports it as `NEW_CONNECTS_LIST_PATH`; `/connections` answers *"This
// screen is not built yet"*, and a walk that went there reported the draft
// missing when it was only looking in the wrong room.
await page.goto(`${BASE}/${TENANT}/accounts?tab=new-connects`, { waitUntil: "networkidle" });
await page.waitForTimeout(3000);
const listText = (await bodyText()).replace(/\s+/g, " ");
// ⚠ **A PARKED NEW CONNECT IS LABELLED BY ITS ADDRESS.**
// `wizard_parks.subject_label` holds `"123707 Reversal Road"`, never the
// owner's name — so a walk hunting for the owner reports the draft missing
// over a list that is showing it. Checked against the column, not guessed.
const resumeLink = page
  .locator("a, button", { hasText: new RegExp(TYPED.address.slice(0, 18).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "i") })
  .first();
let resumedAt = null;
let resumeHow = "no row for this draft was found in the list";
if ((await resumeLink.count()) > 0) {
  await resumeLink.click().catch(() => undefined);
  await page.waitForTimeout(3000);
  resumedAt = await stepNow();
  resumeHow = `opened from the list at ${page.url()}`;
} else {
  // the drafts may live behind a tab; try the parked/draft tab by name
  const tab = page.locator("button, a", { hasText: /^(Parked|Drafts|Unfinished)$/i }).first();
  if ((await tab.count()) > 0) {
    await tab.click().catch(() => undefined);
    await page.waitForTimeout(2500);
    const row = page
      .locator("a, button", { hasText: new RegExp(TYPED.address.slice(0, 18).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "i") })
      .first();
    if ((await row.count()) > 0) {
      await row.click().catch(() => undefined);
      await page.waitForTimeout(3000);
      resumedAt = await stepNow();
      resumeHow = `opened from the parked tab at ${page.url()}`;
    }
  }
}
await shoot("15-resumed");
if (resumedAt === null) {
  blocked(
    "15",
    "a parked draft resumes at the step it was left on",
    `${resumeHow} · parked on step ${parkedAt}${parkRef ? ` as ${parkRef}` : ""} · the list reads: ${listText.slice(0, 300)}`,
  );
} else {
  const values = await readAll();
  check(
    "15",
    "a parked draft resumes at the step it was left on, with its answers",
    resumedAt === parkedAt,
    `parked on step ${parkedAt}, resumed on step ${resumedAt} · ${resumeHow} · owner reads "${values.nc_owner_name}"`,
  );
}

// ════════════════════════════════════════════════════════════════════════════
// CHECKS 17 · 18 · 19 — THE THREE RULES THAT REFUSE A BUILD
// ════════════════════════════════════════════════════════════════════════════
//
// Each is set up from scratch, because each needs a DIFFERENT premise.
async function freshToUnits(addressSuffix, services, premisesPick) {
  await page.goto(`${BASE}/${TENANT}/connections/new`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2200);
  await choose("#nc_owner_kind", "individual_owner");
  await choose("#nc_owner_category");
  await choose("#nc_owner_subcategory", "permanent");
  await segmented("nc_party_kind", "person");
  await page.waitForTimeout(250);
  await fill("#nc_owner_name", `Guardcase ${addressSuffix}`);
  await fill("#nc_owner_email", `guard.${addressSuffix}@example.com`);
  await fill("#nc_ssn", "412-88-7000");
  await choose("#nc_mode", "our_crew");
  await page.waitForTimeout(300);
  if (await forwardBlocked()) return { stopped: "step 1" };
  await forwardButton().click();
  await page.waitForTimeout(1700);

  if (premisesPick !== undefined) {
    await fill("#nc_address", premisesPick);
    await page.waitForTimeout(2800);
    const rows = page.locator("[data-premises-results] button");
    if ((await rows.count()) === 0) return { stopped: `no premises matched "${premisesPick}"` };
    await rows.first().click();
    await page.waitForTimeout(1800);
  } else {
    await fill("#nc_address", `${addressSuffix} Guardrail Way`);
    await page.waitForTimeout(2000);
    await fill("#nc_city", "Austin");
    await fill("#nc_state", "TX");
    await fill("#nc_zip", "78704");
    await choose("#nc_premise_type", "apartment_complex");
  }
  await choose("#nc_scope", premisesPick === undefined ? "new_premise" : undefined);
  await page.waitForSelector("#services_available-add", { timeout: 12000 }).catch(() => undefined);
  const offered = (await has("#services_available-add"))
    ? await page.$$eval("#services_available-add option", (ns) =>
        ns.map((o) => o.value).filter((v) => v !== ""),
      )
    : [];
  for (const code of services === undefined ? offered : services.filter((c) => offered.includes(c))) {
    await page.selectOption("#services_available-add", code).catch(() => undefined);
    await page.waitForTimeout(250);
  }
  await choose("#nc_plan");
  await page.waitForTimeout(1200);
  const said = await refusals();
  if (await forwardBlocked()) return { stopped: "step 2", said, offered };
  await forwardButton().click();
  await page.waitForTimeout(1800);
  await fill("#nc_from", "1");
  await fill("#nc_to", "2");
  await page.waitForTimeout(1300);
  return { at: await stepNow(), offered, said };
}

// ── CHECK 17 · a unit taking a service the street cannot deliver ───────────
console.log("\n── check 17 · a service the street cannot deliver");
const only = await freshToUnits(`${STAMP.slice(8)}a`, ["electric"]);
if (only.at !== 3) {
  blocked("17", "a unit may not take a service the street cannot deliver", `could not reach step 3: ${JSON.stringify(only)}`);
} else {
  // the premise offers ELECTRIC only; try to make a unit take WATER.
  const serviceSelects = page.locator('[data-array="units-and-service-points"] select[data-cell="service"]');
  const optionsHere = await page
    .$$eval('[data-array="units-and-service-points"] select[data-cell="service"] option', (ns) =>
      ns.map((o) => `${o.value}${o.disabled ? "(disabled)" : ""}`),
    )
    .catch(() => []);
  const offersUndeliverable = optionsHere.some((o) => o.startsWith("water") && !o.includes("disabled"));
  let refusedAfterPick = [];
  let movedOn = null;
  if (offersUndeliverable && (await serviceSelects.count()) > 0) {
    await serviceSelects.first().selectOption("water").catch(() => undefined);
    await page.waitForTimeout(1200);
    refusedAfterPick = await refusals();
    const fwd = forwardButton();
    if (!(await forwardBlocked())) {
      await fwd.click();
      await page.waitForTimeout(1500);
      movedOn = await stepNow();
    } else {
      movedOn = 3;
    }
  }
  await shoot("17-undeliverable-service");
  check(
    "17",
    "a unit may NOT take a service the street cannot deliver",
    !offersUndeliverable || (movedOn === 3 && refusedAfterPick.length > 0),
    `the premise was given only [electric]; the per-unit Service list offers ${JSON.stringify(optionsHere.slice(0, 12))}` +
      (offersUndeliverable
        ? ` · after picking water the screen said ${JSON.stringify(refusedAfterPick)} and Continue left us on step ${movedOn}`
        : " · water is NOT offered at all, which is the guard working one layer earlier"),
  );
}

// ── CHECK 18 · sewer without water (TC-NCT-6) ──────────────────────────────
console.log("\n── check 18 · sewer without water (TC-NCT-6)");
const sewerRun = await freshToUnits(`${STAMP.slice(8)}b`, ["electric", "sewer", "water"]);
if (sewerRun.at !== 3) {
  blocked("18", "sewer without water is REFUSED (TC-NCT-6)", `could not reach step 3: ${JSON.stringify(sewerRun)}`);
} else if (!sewerRun.offered.includes("sewer")) {
  blocked(
    "18",
    "sewer without water is REFUSED (TC-NCT-6)",
    `this tenant does not sell sewer — the premise services control offered ${JSON.stringify(sewerRun.offered)}, so the case cannot be built through the UI`,
  );
} else {
  // ⚠ **THE CASE IS REACHED BY TAKING WATER AWAY, NOT BY PICKING SEWER TWICE.**
  // The grid seeds one row per premise service, and a `<select>` already
  // holding `electric` silently refuses `sewer` — so a walk that "sets every
  // row to sewer" ends with `["electric","water","sewer"]` unchanged, never
  // builds the state, and reports TC-NCT-6 unenforced over a guard that works.
  // That is law 7's *looking at the wrong thing*, and it cost this lane a
  // false FAIL before the select values were read back.
  //
  // Every unit group is expanded first, because a collapsed unit's rows are
  // not in the DOM at all — a second way to measure half the table.
  const groups = page.locator('[data-array="units-and-service-points"] tbody tr [aria-expanded="false"]');
  const gn = await groups.count();
  for (let k = 0; k < gn; k += 1) {
    await groups.nth(k).click().catch(() => undefined);
    await page.waitForTimeout(300);
  }
  await page.waitForTimeout(700);
  const before18 = await page.$$eval(
    '[data-array="units-and-service-points"] select[data-cell="service"]', (ns) => ns.map((n) => n.value));
  for (let pass = 0; pass < 10; pass += 1) {
    const removed = await page.evaluate(() => {
      const sels = Array.from(
        document.querySelectorAll('[data-array="units-and-service-points"] select[data-cell="service"]'));
      const at = sels.findIndex((s) => s.value === "water");
      if (at === -1) return "done";
      const x = sels[at].closest("tr")?.querySelector("[data-remove-row]");
      if (!x || x.disabled) return "refused";
      x.click();
      return "removed";
    });
    if (removed !== "removed") break;
    await page.waitForTimeout(700);
  }
  await page.waitForTimeout(1500);
  const said = await refusals();
  const disabled = await forwardBlocked();
  let moved = 3;
  if (!disabled) {
    await forwardButton().click();
    await page.waitForTimeout(1800);
    moved = await stepNow();
  }
  await shoot("18-sewer-without-water");
  check(
    "18",
    "sewer with no water on the unit is REFUSED, not warned (TC-NCT-6)",
    moved === 3 && (said.some((t) => /sewer/i.test(t)) || disabled),
    `the grid opened as ${JSON.stringify(before18)}; every water row was removed, leaving sewer with no water on the unit · ` +
      `Continue disabled=${disabled} · landed on step ${moved} · the screen says ${JSON.stringify(said).slice(0, 300)}`,
  );
}

// ── CHECK 19 · a premises that already takes that service ──────────────────
console.log("\n── check 19 · a premises that already has that service");
const taken = await freshToUnits(`${STAMP.slice(8)}c`, undefined, process.env.NC_EXISTING_ADDRESS ?? "1408 Bluestem");
const wholeScreen = (await bodyText()).replace(/\s+/g, " ");
const saysMoveIn = /move[- ]?in/i.test(wholeScreen);
const said19 = await refusals();
await shoot("19-premises-already-served");
check(
  "19",
  "a premises that already takes the service says *raise a move-in instead*",
  saysMoveIn,
  `picked an existing premises · reached step ${taken.at ?? "(stopped: " + JSON.stringify(taken) + ")"} · ` +
    `refusals on screen ${JSON.stringify(said19).slice(0, 250)} · ` +
    (saysMoveIn
      ? `the phrase "move-in" IS on the screen: ${(wholeScreen.match(/.{0,70}move[- ]?in.{0,70}/i) ?? [""])[0]}`
      : "the words *move-in* appear NOWHERE on the screen"),
);

writeFileSync(join(OUT, "00-RESULTS.json"), JSON.stringify({ stamp: STAMP, results }, null, 2) + "\n");
const failed = results.filter((r) => r.verdict === "FAIL").length;
const blockedN = results.filter((r) => r.verdict === "BLOCKED").length;
console.log(`\n── ${results.filter((r) => r.verdict !== "NOTE").length} checks · ${failed} FAIL · ${blockedN} BLOCKED`);
console.log(`── ${OUT}/00-RESULTS.json`);
await browser.close();
process.exit(0);
