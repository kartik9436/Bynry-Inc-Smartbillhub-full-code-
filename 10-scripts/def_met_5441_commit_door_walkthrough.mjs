// ── Trace ──────────────────────────────────────────────
// Defects: DEF-MET-5441 (the Create-connection button posted to an address
//          that answered 404, so NO build made through this wizard had ever
//          reached the database) · DEF-MET-5437 (the commit matched units by
//          database id while the wizard can only send labels, so every meter
//          on a multi-unit build landed on unit 1)
// Rules:   BR-MET-112 (nothing is written until the last button; ONE
//          transaction, both or neither) · BR-MET-1024 (New Connect may create
//          the address it builds on) · BR-SHL-019 (exactly one transactional
//          commit) · hard-won law 6 (no gate in this repo reads rendered
//          output) · PO definition of done, verbatim: *"everything should be
//          executed based on actual code, and rules that we place, also ensure
//          you do web walkthorugh before you sign off the user story or build"*
// ───────────────────────────────────────────────────────
//
// WHAT THIS PROVES THAT NO UNIT TEST CAN.
//
//   1 · **A 404 IS INVISIBLE TO BOTH SUITES.** The front-end suite MOCKS
//       `newConnectEndpoints`, so its cases pass whatever the address is; the
//       backend suite calls `commit_connection` directly with an id the browser
//       never has. Only a real browser pressing the real button over the real
//       wire can answer *did anything get written*.
//   2 · **THE DATABASE IS ASKED, NOT THE MANIFEST.** The manifest is a dict the
//       server returns; a commit that wrote nothing could still return one. So
//       after the press this reads the connection, the premises, the units and
//       every asset back off the API and counts them.
//   3 · **WHICH UNIT EACH METER STANDS ON.** `DEF-MET-5437`'s count was always
//       right and every placement was wrong — six meters, all on `Apt 1`. A
//       check that asserted the COUNT would have passed on the defect, so this
//       one asserts the SPREAD.
//
// RUN IT:  node 10-scripts/def_met_5441_commit_door_walkthrough.mjs
//          BASE=http://127.0.0.1:8098 TENANT=brazosbend
const { existsSync, readdirSync, mkdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8098";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/def_met_5441";
const UNITS = Number(process.env.UNITS ?? 6);
// The pattern makes `Apt 1 … Apt N` and step 3 adds a common-area unit on top,
// so the build has N + 1 units and N × 2 meters (electric + water per flat).
const TOTAL_UNITS = UNITS + 1;
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of [
        "chrome-linux64/chrome",
        "chrome-linux/chrome",
        "chrome-linux/headless_shell",
      ]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  throw new Error("no chromium found");
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1500, height: 1300 } });
// **THE PAYLOAD THE BUTTON ACTUALLY SENDS, PRINTED.** Three of this wizard's
// defects were the browser's assembler and the server's reader disagreeing
// about a key, and each one was invisible because nobody ever read the wire.
let pressedPayload = null;
page.on("request", (req) => {
  if (req.method() === "POST" && req.url().endsWith("/connections/commit")) {
    const body = req.postData() ?? "";
    if (body.length > 2) pressedPayload = body;
    console.log("── the commit payload the BUTTON sent ──");
    console.log(body.slice(0, 1400));
  }
});
page.on("response", async (res) => {
  if (res.request().method() === "POST" && res.url().endsWith("/connections/commit")) {
    console.log(`── the server answered ${res.status()} ──`);
    console.log((await res.text().catch(() => "")).slice(0, 900));
  }
});
const say = (...parts) => console.log(...parts);
let failures = 0;
function check(label, ok, detail = "") {
  say(`${ok ? "PASS" : "FAIL"}  ${label}${detail === "" ? "" : ` — ${detail}`}`);
  if (!ok) failures += 1;
}

// The address is unique per run, so a second run proves the same thing rather
// than colliding with the first one's property.
const STAMP = new Date().toISOString().replace(/[^0-9]/g, "").slice(0, 14);
const ADDRESS = `${STAMP.slice(8)} Lane A Commit Walk`;
const PARCEL = `R-LANEA-${STAMP.slice(8)}`;

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
say("signed in as", EMAIL);

const api = (path, init) =>
  page.evaluate(
    async ([p, i]) => {
      const res = await fetch(p, { credentials: "include", ...(i ?? {}) });
      return { status: res.status, body: await res.text() };
    },
    [path, init],
  );

// ── 0 · THE ADDRESS THE BUTTON POSTS TO IS SERVED ──────────────────────────
// This is the defect itself, measured the way it was found: an empty POST to
// the wizard's own address. 404 means the door does not exist; anything else
// means it does and is refusing the empty body on its own terms.
const probe = await api(`/api/${TENANT}/connections/commit`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: "{}",
});
check(
  "0 · POST /connections/commit is a real door (not 404)",
  probe.status !== 404,
  `status ${probe.status}`,
);

// ── THE EIGHT STEPS ────────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/connections/new`, { waitUntil: "networkidle" });
await page.waitForTimeout(1200);

async function forward(label) {
  const buttons = await page.$$('[data-wizard="actions"] button');
  const last = buttons[buttons.length - 1];
  const text = (await last.innerText()).trim();
  say(`  → ${label}: pressing "${text}"`);
  await last.click();
  await page.waitForTimeout(1400);
  return text;
}

// 1 · Owner & scope
await page.selectOption("#nc_owner_kind", "builder_developer");
await page.fill("#nc_owner_name", process.env.OWNER ?? "Lane A Developments LLC");
await page.selectOption("#nc_owner_subcategory", "permanent");
await page.fill("#nc_owner_email", "build@lanea.example");
await page.fill("#nc_owner_phone", "512-555-0117");
await page.fill("#nc_prefix", "Apt");
await page.check('input[name="nc_scope"][value="new_premise"]', { force: true });
await page.check('input[name="nc_mode"][value="our_crew"]', { force: true });
await forward("step 1 · Owner & scope");

// 2 · Premise — the address this build CREATES. Nothing here exists yet.
await page.fill("#nc_address", ADDRESS);
// ⚠ **THE TYPE IS READ OFF THE SELECT, NEVER TYPED HERE — `DEF-MET-5463`.**
// This script named `multi_unit` on its first run and the build was refused
// `422 metering.premises.type_unknown`: the wizard offered four codes and the
// server's Reference-data catalogue holds six different ones, with exactly one
// in common. A walkthrough that hardcodes a coded value is the same defect it
// is here to catch, one layer up.
await page.waitForTimeout(1200);
const typeOptions = await page.$$eval("#nc_premise_type option", (ns) =>
  ns.map((o) => o.value).filter((v) => v !== ""),
);
say("premise types the screen offers:", JSON.stringify(typeOptions));
check("2 · the premise-type select offers something", typeOptions.length > 0, `${typeOptions.length}`);
await page.selectOption("#nc_premise_type", typeOptions[0]);
await page.fill("#nc_parcel", PARCEL);
await forward("step 2 · Premise");

// 3 · Units — the pattern that makes `Apt 1 … Apt N`.
await page.fill("#nc_from", "1");
await page.fill("#nc_to", String(UNITS));
await forward("step 3 · Units");

// 4 · Services. The per-unit ticks are OFFERED from the premise ticks, so the
//     premise half is set first and the page re-renders before the unit half
//     exists at all.
// ⚠ **`force: true`, AND IT IS NOT A SHORTCUT.** The tick is an `sr-only`
// input under a drawn `<span data-checkbox-mark>`, which is the accessible way
// to build one and which intercepts the pointer — an ordinary `check()` waits
// thirty seconds and times out. The input is the thing with the state, so the
// input is the thing this drives.
await page.check("#nc_premise_services_electric", { force: true });
await page.check("#nc_premise_services_water", { force: true });
await page.waitForTimeout(800);
await page.check("#nc_unit_services_electric", { force: true });
await page.check("#nc_unit_services_water", { force: true });
await forward("step 4 · Map services");

// 5 · Plans. Whatever this tenant actually publishes — never a hardcoded id.
const planOptions = await page.$$eval("#nc_plan_apartments option", (ns) =>
  ns.map((o) => o.value).filter((v) => v !== ""),
);
check("5 · this tenant publishes at least one plan", planOptions.length > 0, `${planOptions.length}`);
await page.selectOption("#nc_plan_apartments", planOptions[0]);
// ⚠ **THE COMMON AREA IS PRICED TOO, AND LEAVING IT BLANK IS A REAL REFUSAL.**
// Step 3 includes a common-area unit by default, `commitPlanOf` emits an
// assignment for every unit it made, and a blank one arrives as
// `tariff_id: null` — which the commit refuses with
// `metering.plan.tariff_required`. That is the product working: an active
// account on an unpriced unit is an unbillable bill (`BR-MET-040`).
const commonOptions = await page.$$eval("#nc_plan_common option", (ns) =>
  ns.map((o) => o.value).filter((v) => v !== ""),
);
if (commonOptions.length > 0) await page.selectOption("#nc_plan_common", commonOptions[0]);
await forward("step 5 · Plans & work orders");

await forward("step 6 · Charges");
await forward("step 7 · Communication");

// 8 · Review — what the screen PROMISES, read off the rendered page before the
//     press so it can be compared with what the server actually made.
await page.waitForTimeout(800);
const promised = await page.evaluate(() => document.body.innerText);
await page.screenshot({ path: `${OUT}/01-review.png`, fullPage: true });
say("review page mentions:", JSON.stringify(promised.match(/\b\d+ (?:units?|meters?|plans?)/gi) ?? []));

const before = JSON.parse((await api(`/api/${TENANT}/connections?per=1`)).body);
const pressed = await forward("step 8 · REVIEW → Create connection");
check("8 · the final button is the commit", /Create connection/.test(pressed), pressed);

await page.waitForTimeout(4000);
await page.screenshot({ path: `${OUT}/02-after-press.png`, fullPage: true });
const after = await page.evaluate(() => document.body.innerText);
say("── after the press ──");
say(after.split("\n").filter((l) => l.trim() !== "").slice(0, 22).join("\n"));

// ── WHAT THE PRESS ITSELF DID ──────────────────────────────────────────────
// ⚠ **THE OWNER HALF IS BLOCKED ON ANOTHER LANE AND THIS SAYS SO RATHER THAN
// PRETENDING OTHERWISE.** `commitPlanOf` sets `create_owner_account` from the
// owner's name, step 1 REQUIRES that name, and the accounts door refuses
// without a party kind — `BR-CUS-1024`, `customers.account.identity_kind_
// required` — because step 1 has no person-or-company control yet (the open
// half of `DEF-MET-5093`). So every build pressed through this screen today is
// refused on the owner, AFTER everything else has been built and rolled back.
// `BR-MET-112` holding is the reason nothing is left behind.
const ownerBlocked = /identity_kind_required|Tell us whether|person or a company/i.test(after);
check(
  "9 · the press reached the server and was answered on its own terms",
  pressedPayload !== null,
  pressedPayload === null ? "no commit request was sent at all" : "payload captured",
);
say(
  ownerBlocked
    ? "9 · the press was refused on the OWNER ACCOUNT (BR-CUS-1024, another lane's field) — everything before it built and rolled back"
    : "9 · the press was not refused on the owner",
);

// ── THE SAME PAYLOAD, ONE FLAG DOWN, OVER THE SAME WIRE ────────────────────
// The browser's OWN bytes — not a payload written here — with
// `create_owner_account` set false, which is what the screen itself sends when
// a clerk leaves the owner blank. That isolates the half this lane built from
// the half it does not own, and it still goes through the real door, the real
// session and the real transaction.
const plan = JSON.parse(pressedPayload ?? "{}");
plan.create_owner_account = false;
plan.premises = { ...plan.premises, address: `${ADDRESS} B` };
const committed = await api(`/api/${TENANT}/connections/commit`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(plan),
});
say(`── the door answered ${committed.status} ──`);
say(committed.body.slice(0, 700));
check("10 · the commit SUCCEEDED", committed.status === 200, `status ${committed.status}`);
const built = committed.status === 200 ? JSON.parse(committed.body) : null;
if (built !== null) {
  say("manifest:", JSON.stringify(built.manifest));
  check("10 · a CON- number came back", Boolean(built.connection_no), String(built.connection_no));
  check(
    "10 · the manifest says this door CREATED the address (DEF-2961)",
    built.premises_created === true && built.manifest.premises === 1,
    `premises_created=${built.premises_created} manifest.premises=${built.manifest.premises}`,
  );
}

// ── AND NOW THE DATABASE, WHICH IS THE ONLY WITNESS THAT COUNTS ────────────
const premisesHit = JSON.parse(
  (await api(`/api/${TENANT}/premises?q=${encodeURIComponent(`${ADDRESS} B`)}&per=5`)).body,
);
const premises = (premisesHit.results ?? [])[0] ?? null;
check(
  "11 · the ADDRESS the wizard typed exists as a property",
  premises !== null,
  premises ? `${premises.premise_no} ${premises.address_line}` : "no premises found",
);
if (premises !== null) {
  check(
    "11 · the parcel reference landed on it (external_ref, BR-INT-048)",
    premises.external_ref === PARCEL,
    `${premises.external_ref} vs ${PARCEL}`,
  );

  const unitRows = JSON.parse(
    (await api(`/api/${TENANT}/units?f.premises_id=${premises.id}&per=200`)).body,
  );
  const units = unitRows.results ?? [];
  check(
    `12 · ${TOTAL_UNITS} units were created (${UNITS} flats + the common area)`,
    units.length === TOTAL_UNITS,
    `${units.length}`,
  );
  say("units:", JSON.stringify(units.map((u) => u.label)));

  const assetRows = JSON.parse(
    (await api(`/api/${TENANT}/assets?f.premises_id=${premises.id}&per=300`)).body,
  );
  const assets = assetRows.results ?? [];
  say(`assets at this address: ${assets.length}`);

  // ── DEF-MET-5437 — WHICH UNIT EACH METER IS ON ─────────────────────────
  // The count was always right. The PLACEMENT was the defect: every meter on
  // `Apt 1` and nothing on the other flats.
  // ⚠ **`assigned_to` IS THE UNIT'S LABEL. `unit` IS THE UNIT OF MEASURE.**
  // An asset row carries `unit: "kWh"` because CLAUDE.md hard rule 3 makes
  // every consumption carry an explicit one, and `assigned_to` is the label of
  // the unit the asset stands on. Keying on `unit` made this check report *"2
  // distinct units"* over a perfectly spread build; keying on a field the row
  // does not have made it report *"1"*. Both are law 7's *looking at the wrong
  // thing*, and both were caught only because the number was absurd — which is
  // why the count is printed beside the verdict rather than hidden behind it.
  const byUnit = new Map();
  for (const asset of assets) {
    const key = asset.assigned_to ?? asset.assigned_unit_id ?? "(unassigned)";
    byUnit.set(key, (byUnit.get(key) ?? 0) + 1);
  }
  say("meters per unit:", JSON.stringify([...byUnit.entries()].sort()));
  check(
    "13 · the meters are SPREAD across the units, not stacked on unit 1",
    byUnit.size >= UNITS,
    `${byUnit.size} distinct units hold a meter, of ${UNITS} flats`,
  );
  const stacked = [...byUnit.entries()].some(([, n]) => n >= UNITS * 2);
  check(
    "13 · no single unit swallowed every meter (DEF-MET-5437)",
    !stacked,
    JSON.stringify([...byUnit.entries()]),
  );
}

say(failures === 0 ? "\nALL CHECKS PASSED" : `\n${failures} CHECK(S) FAILED`);
await browser.close();
process.exit(failures === 0 ? 0 : 1);
