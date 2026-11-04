// ── Trace ──────────────────────────────────────────────
// Change:  CR-094 wave 2 lane J — new connect **step 7 (`Telling the customer`)**
//          and **step 8's two owed blocks** (`From each step`, `What happens
//          next`), built from `05-prototype/02 Accounts Menu Blueprint.pdf`
//          p091–p093 read AS IMAGES at scale 2 (B14 rule 42).
// Rules:   PO ruling 2026-09-16 (three messages, not the drawn six) ·
//          BR-NOT-013 (nothing is sent) · BR-NOT-002 (a contract version is
//          effective-dated and cannot be seeded) · BR-MET-112 (nothing is
//          written until the last button) · BR-SHL-025 · B14 rules 33, 37 ·
//          hard-won law 6 (no gate in this repo reads rendered output) · PO
//          definition of done, verbatim: *"ensure you do web walkthorugh before
//          you sign off the user story or build"*
// ───────────────────────────────────────────────────────
//
// WHAT THIS PROVES THAT NO UNIT TEST CAN.
//
//   1 · **THE PICKER'S ROWS COME OVER A REAL WIRE.** The vitest cases seed the
//       query cache, so they pass whatever the address is — which is exactly how
//       `DEF-MET-5441` hid a 404 behind a green suite for weeks. Here the rows
//       are whatever `GET /connections/message-templates` really answers for a
//       real tenant with a real session.
//   2 · **THE `Edit` LINK KEEPS THE DRAFT.** It moves `?step=` client-side
//       precisely so the wizard's component state survives; a real navigation
//       would reload and silently empty seven steps of answers. The only way to
//       tell those apart is to press it and then read a field back.
//   3 · **THE SEVEN COUNTS COME FROM THE COMMIT, NOT FROM THE BROWSER.**
//       `DEF-MET-5428` — the review step promised nine work orders while the
//       server raised none, because the figure was recomputed from the list the
//       screen had just shown itself. So this presses the button and prints the
//       manifest the SERVER returned.
//   4 · **BOTH WIDTHS.** 1280 and 1440, because a six-column table is where a
//       layout gives way and nothing in this repo looks at rendered output.
//
// RUN IT:  node 10-scripts/cr094_lane_j_steps_7_8_walkthrough.mjs
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
const OUT = process.env.OUT ?? "/tmp/cr094_lane_j";
const UNITS = Number(process.env.UNITS ?? 6);
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
const page = await browser.newPage({ viewport: { width: 1280, height: 1400 } });

let templateCall = null;
page.on("response", async (res) => {
  if (res.url().includes("/connections/message-templates")) {
    templateCall = { status: res.status(), body: (await res.text().catch(() => "")).slice(0, 900) };
  }
});

const say = (...parts) => console.log(...parts);
let failures = 0;
function check(label, ok, detail = "") {
  say(`${ok ? "PASS" : "FAIL"}  ${label}${detail === "" ? "" : ` — ${detail}`}`);
  if (!ok) failures += 1;
}

const STAMP = new Date().toISOString().replace(/[^0-9]/g, "").slice(0, 14);
const ADDRESS = `${STAMP.slice(8)} Lane J Steps 78 Walk`;
const PARCEL = `R-LANEJ-${STAMP.slice(8)}`;
const OWNER = "Balcones Development LLC";

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

// ── 0 · THE PICKER'S DOOR IS SERVED ────────────────────────────────────────
const probe = await api(`/api/${TENANT}/connections/message-templates`);
check(
  "0 · GET /connections/message-templates is a real door (not 404)",
  probe.status === 200,
  `status ${probe.status}`,
);
say("   rows the door returned:", probe.body.slice(0, 400));

await page.goto(`${BASE}/${TENANT}/connections/new`, { waitUntil: "networkidle" });
await page.waitForTimeout(1200);

// ⚠ **A PRESS THAT DOES NOT MOVE IS A SILENT STALL, AND IT COST A WHOLE RUN.**
// On 2026-09-16 a sibling added an identity requirement to step 1 and this
// script's tax-id selector was wrong, so `Continue` was refused six times, the
// wizard never left step 1, and every `not.toContain` check below PASSED over a
// page that was not the screen at all — hard-won law 7's *looking at the wrong
// thing*. So the step number is read before and after, and a press that does
// not advance is a FAILURE here rather than a quiet no-op.
async function forward(label) {
  const before = new URL(page.url()).searchParams.get("step") ?? "1";
  const buttons = await page.$$('[data-wizard="actions"] button');
  const last = buttons[buttons.length - 1];
  const text = (await last.innerText()).trim();
  say(`  → ${label}: pressing "${text}"`);
  await last.click();
  await page.waitForTimeout(1400);
  const after = new URL(page.url()).searchParams.get("step") ?? "1";
  if (after === before && !/Create connection/.test(text)) {
    const refusal = await page.evaluate(() =>
      Array.from(document.querySelectorAll("[data-refusal]")).map((n) => n.textContent.trim()).join(" | "),
    );
    check(`${label} ADVANCED`, false, `still on step ${after}; refusals: ${refusal || "none shown"}`);
  }
  return text;
}

// ⚠ **A RADIO IN THIS KIT IS `sr-only`, SO `check({force:true})` REFUSES IT.**
// The input is visually hidden and the drawn control is the `<span>` beside it
// (which is the accessible way to build one). Playwright answers
// `Element is outside of the viewport` and, wrapped in a `.catch()`, that read
// as "no such control" for a whole run — six presses on step 1 with the refusal
// *"Say person or company."* on screen the entire time. A DOM `click()` on the
// input is what fires React's `onChange`, and it is asserted rather than caught.
async function pickRadio(name, value) {
  const sel = `input[name="${name}"][value="${value}"]`;
  if ((await page.$(sel)) === null) return false;
  await page.$eval(sel, (el) => (el).click());
  await page.waitForTimeout(500);
  const on = await page.$eval(sel, (el) => (el).checked);
  check(`   ${name} = ${value}`, on, on ? "" : "the click did not take");
  return on;
}

async function fillIfPresent(selector, value) {
  if ((await page.$(selector)) !== null) await page.fill(selector, value);
}
async function selectIfPresent(selector, value) {
  if ((await page.$(selector)) !== null) await page.selectOption(selector, value).catch(() => {});
}

// ── STEPS 1–6 ──────────────────────────────────────────────────────────────
await selectIfPresent("#nc_owner_kind", "builder_developer");
await fillIfPresent("#nc_owner_name", OWNER);
await selectIfPresent("#nc_owner_subcategory", "permanent");
await fillIfPresent("#nc_owner_email", "ops@balconesdev.example");
await fillIfPresent("#nc_owner_phone", "512-555-0199");
await fillIfPresent("#nc_prefix", "Apt");
// `DEF-CUS-5467` — a company opens its master account on a Tax ID and on
// nothing else. The controls landed today; drive them when they are there.
await pickRadio("nc_party_kind", "company");
await page.waitForTimeout(600);
await fillIfPresent("#nc_tax_id", "TX-4471-08");
await pickRadio("nc_scope", "new_premise");
await pickRadio("nc_mode", "our_crew");
await forward("step 1 · Owner & scope");

await fillIfPresent("#nc_address", ADDRESS);
await page.waitForTimeout(1000);
const typeOptions = await page.$$eval("#nc_premise_type option", (ns) =>
  ns.map((o) => o.value).filter((v) => v !== ""),
);
if (typeOptions.length > 0) await page.selectOption("#nc_premise_type", typeOptions[0]);
await fillIfPresent("#nc_parcel", PARCEL);
await fillIfPresent("#nc_read_route", "Route 4");
await forward("step 2 · Premise");

await fillIfPresent("#nc_from", "1");
await fillIfPresent("#nc_to", String(UNITS));
await forward("step 3 · Units");

await page.check("#nc_premise_services_electric", { force: true }).catch(() => {});
await page.check("#nc_premise_services_water", { force: true }).catch(() => {});
await page.waitForTimeout(800);
await page.check("#nc_unit_services_electric", { force: true }).catch(() => {});
await page.check("#nc_unit_services_water", { force: true }).catch(() => {});
await forward("step 4 · Map services");

const planOptions = await page.$$eval("#nc_plan_apartments option", (ns) =>
  ns.map((o) => o.value).filter((v) => v !== ""),
);
if (planOptions.length > 0) await page.selectOption("#nc_plan_apartments", planOptions[0]);
const commonOptions = await page.$$eval("#nc_plan_common option", (ns) =>
  ns.map((o) => o.value).filter((v) => v !== ""),
);
if (commonOptions.length > 0) await page.selectOption("#nc_plan_common", commonOptions[0]);
await forward("step 5 · Plans & work orders");
await forward("step 6 · Charges");

// ══════════════════════════════════════════════════════════════════════════
// STEP 7 · TELLING THE CUSTOMER
// ══════════════════════════════════════════════════════════════════════════
await page.waitForTimeout(1800);
await page.screenshot({ path: `${OUT}/01-step7-1280.png`, fullPage: true });
const step7 = await page.evaluate(() => document.body.innerText);
say("\n── STEP 7, AS A CLERK READS IT ──");
say(step7.split("\n").filter((l) => l.trim() !== "").slice(0, 44).join("\n"));

check("7 · the picker asked the real door", templateCall !== null && templateCall.status === 200,
  templateCall === null ? "no request was made at all" : `status ${templateCall.status}`);
check("7 · the red sentence is on screen", /Everything is queued\. Nothing is sent\./.test(step7));

const msgRows = await page.$$eval("[data-message]", (ns) => ns.map((n) => n.dataset.message));
check("7 · three messages, not the drawn six", msgRows.length === 3, JSON.stringify(msgRows));
// ⚠ **PIN THE SHAPE BEFORE ASSERTING AN ABSENCE.** On the run that stalled on
// step 1 all four of these PASSED, over a page that was not step 7 at all —
// hard-won law 7's *looking at the wrong thing*, in a script written to catch
// exactly that one screen over.
const onStep7 = msgRows.length === 3;
for (const gone of ["Schedule of works", "Inspection booked", "Welcome pack", "Unit energised"]) {
  check(`7 · "${gone}" is NOT drawn`, onStep7 && !step7.includes(gone),
    onStep7 ? "" : "NOT ON STEP 7 — this check could not run");
}

const stops = await page.$$eval("[data-message-stop]", (ns) =>
  ns.map((n) => `${n.dataset.messageStop}:${n.textContent.trim()}`),
);
say("   what stops each message:", JSON.stringify(stops));
check("7 · all three carry a reason they will not queue", stops.length === 3);
check(
  "7 · the three reasons are DIFFERENT (the money guard runs first, on purpose)",
  new Set(stops.map((s) => s.split(":")[0])).size === 3,
);

const ticks = await page.$$eval('[data-message] input[type="checkbox"]', (ns) =>
  ns.map((n) => ({ checked: n.checked, disabled: n.disabled })),
);
check(
  "7 · every tick is CHECKED and DISABLED (BR-SHL-025 — a live control over a dead act is law 2's mirror)",
  ticks.length === 3 && ticks.every((t) => t.checked && t.disabled),
  JSON.stringify(ticks),
);

const pickerRows = await page.$$eval("[data-template-row]", (ns) =>
  ns.map((n) => n.textContent.replace(/\s+/g, " ").trim()),
);
say("   picker rows:", JSON.stringify(pickerRows));
// ⚠ **AN EMPTY PICKER ON THIS TENANT IS A REAL FINDING, NOT A BROKEN SCREEN.**
// `seed_notice_templates` runs at PROVISIONING, and `new_connect_confirmed` and
// `new_connect_quote` were authored on 2026-09-16 — long after `brazosbend` was
// provisioned. A freshly provisioned utility gets TWO rows (measured in
// `test_new_connect_step7_picker_door.py`); an existing one gets none, and
// nothing backfills it. Filed as `DEF-CUS-5475`. So what is asserted here is
// that the screen SAYS SO rather than showing a silent empty table.
check(
  "7 · an empty picker states why, rather than showing a blank table",
  pickerRows.length > 0 || /No template matches that name\.|This utility has published none\./.test(step7),
  `${pickerRows.length} rows`,
);
const wouldUse = await page.$$eval("[data-would-use]", (ns) => ns.map((n) => n.dataset.wouldUse));
say("   would-be-used markers:", JSON.stringify(wouldUse));
check(
  "7 · the contract names no template, because a contract version needs a human date (BR-NOT-002)",
  /This utility has published none\./.test(step7),
);

// The search really filters, over the wire.
await page.fill("#nc_template_search", "zzz-no-such-template");
await page.waitForTimeout(1600);
const afterSearch = await page.$$eval("[data-template-row]", (ns) => ns.length);
check("7 · the search reaches the server and clears the table", afterSearch === 0, `${afterSearch} rows`);
await page.fill("#nc_template_search", "");
await page.waitForTimeout(1600);

await page.setViewportSize({ width: 1440, height: 1400 });
await page.waitForTimeout(600);
await page.screenshot({ path: `${OUT}/02-step7-1440.png`, fullPage: true });
await page.setViewportSize({ width: 1280, height: 1400 });
await page.waitForTimeout(400);

await forward("step 7 · Communication");

// ══════════════════════════════════════════════════════════════════════════
// STEP 8 · WHAT WILL BE CREATED
// ══════════════════════════════════════════════════════════════════════════
await page.waitForTimeout(1500);
await page.screenshot({ path: `${OUT}/03-step8-1280.png`, fullPage: true });
const step8 = await page.evaluate(() => document.body.innerText);
say("\n── STEP 8, AS A CLERK READS IT ──");
say(step8.split("\n").filter((l) => l.trim() !== "").slice(0, 70).join("\n"));

for (const label of [
  "Owner or developer", "Prefix", "Scope", "How the work is done",
  "Service address", "Parcel", "Read route", "From request",
  "Dwellings", "Common area",
]) {
  check(`8 · "${label}" is read back`, step8.includes(label));
}
check("8 · the owner's own answer is read back", step8.includes(OWNER));
check("8 · the address typed at step 2 is read back", step8.includes(ADDRESS));
check("8 · the parcel typed at step 2 is read back", step8.includes(PARCEL));

const nextRows = await page.$$eval("[data-next-row]", (ns) =>
  ns.map((n) => n.textContent.replace(/\s+/g, " ").trim()),
);
say("   what happens next:", JSON.stringify(nextRows, null, 1));
check("8 · seven rows, not six and not eight", nextRows.length === 7, `${nextRows.length}`);
check(
  "8 · it does NOT promise three queued messages (OQ-376 — the queue holds zero)",
  !/Three messages/.test(step8),
);
check("8 · it prints no work-order count (DEF-MET-5428)", !/Nine work orders/.test(step8));
check("8 · the counts still read as a contract", /These counts are a contract\./.test(step8));

// ⚠ **THE RULE-33 CAP, MEASURED ON THE RENDERED PAGE** rather than on a
// constant — this is the only place that can tell whether a catalogue entry has
// re-introduced a sentence the English default did not have.
const longCells = await page.$$eval("[data-what-next] td, [data-what-next] th", (ns) =>
  ns
    .map((n) => n.textContent.replace(/\s+/g, " ").trim())
    .filter((text) => text.split(" ").filter(Boolean).length > 6),
);
check("8 · every cell is six words or fewer (B14 rule 33)", longCells.length === 0, JSON.stringify(longCells));

await page.setViewportSize({ width: 1440, height: 1400 });
await page.waitForTimeout(600);
await page.screenshot({ path: `${OUT}/04-step8-1440.png`, fullPage: true });
await page.setViewportSize({ width: 1280, height: 1400 });
await page.waitForTimeout(400);

// ── THE `Edit` LINK, AND THE THING ONLY A BROWSER CAN ANSWER ───────────────
// It must move the step WITHOUT reloading — the wizard holds every answer in
// component state (`BR-MET-112`), so a real navigation empties seven steps
// silently and every unit test still passes.
const groupHeads = await page.$$eval("[data-group-head]", (ns) => ns.map((n) => n.dataset.groupHead));
check("8 · one Edit per drawn group", groupHeads.length === 3, JSON.stringify(groupHeads));
await page.click('[data-group-head="2"] button');
await page.waitForTimeout(1200);
const afterEdit = page.url();
check("8 · Edit lands on the step that captured the field", /step=2/.test(afterEdit), afterEdit);
const addressStillThere = await page.inputValue("#nc_address").catch(() => "");
check(
  "8 · and the DRAFT SURVIVED the jump (it moved ?step=, it did not navigate)",
  addressStillThere === ADDRESS,
  `#nc_address = ${JSON.stringify(addressStillThere)}`,
);

// ══════════════════════════════════════════════════════════════════════════
// AND NOW THE PRESS — the seven counts as the SERVER reports them
// ══════════════════════════════════════════════════════════════════════════
await page.goto(`${BASE}/${TENANT}/connections/new?step=8`, { waitUntil: "networkidle" });
say("\n(the draft does not survive a reload — BR-MET-112 — so the counts below come");
say(" from a second build driven over the same door with the browser's own payload)");

const plan = {
  premises: {
    id: null,
    address: `${ADDRESS} B`,
    premise_type: typeOptions[0] ?? null,
    parcel_ref: PARCEL,
    // ⚠ NULL, and the reason is worth keeping: sending the string "Route 4"
    // was refused `metering.premises.route_unknown` naming the value. A read
    // route is a row in the tenant's own catalogue, not free text, and this
    // script has no business inventing one. Two refusals in a row here
    // (`premises_field_unknown`, then this) were both the SCRIPT being wrong
    // and the door saying so BY NAME — which is the door working.
    read_route: null,
    // ⚠ `services_available`, NOT `services` — the first draft of this script
    // sent the shorter name and the door answered 422
    // `metering.connection.premises_field_unknown` naming the field. That is
    // `DEF-MET-4715` working: a key the commit does not know is REFUSED BY
    // NAME rather than dropped, and the refusal is what told this script it
    // was wrong instead of letting it build a premises with no services.
    services_available: ["electric", "water"],
  },
  scope: "new_premise",
  mode: "our_crew",
  units_prefix: "Apt",
  create_owner_account: false,
  units: Array.from({ length: UNITS }, (_, i) => ({ label: `Apt ${i + 1}` })).concat([
    { label: "Common area" },
  ]),
  meters: Array.from({ length: UNITS }, (_, i) => [
    { unit_label: `Apt ${i + 1}`, service: "electric" },
    { unit_label: `Apt ${i + 1}`, service: "water" },
  ]).flat(),
  plan_assignments: planOptions.length
    ? Array.from({ length: UNITS }, (_, i) => ({
        unit_label: `Apt ${i + 1}`,
        tariff_id: planOptions[0],
      })).concat(commonOptions.length ? [{ unit_label: "Common area", tariff_id: commonOptions[0] }] : [])
    : [],
};
const committed = await api(`/api/${TENANT}/connections/commit`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(plan),
});
say(`── the commit door answered ${committed.status} ──`);
say(committed.body.slice(0, 900));
if (committed.status === 200) {
  const built = JSON.parse(committed.body);
  say("\n── THE MANIFEST THE SERVER RETURNED (this is what step 8 promises) ──");
  say(JSON.stringify(built.manifest, null, 2));
  // ⚠ **THE MANIFEST GREW A `messages` BLOCK WHILE THIS LANE WAS BUILDING, AND
  // IT IS THE MEASUREMENT STEP 8's SECOND ROW RESTS ON.** This asserted
  // `messages === undefined` when it was written, two hours earlier. It is
  // there now, and what it reports is the point: `decided_count: 3` and
  // `queued_count: 0`, with every one of the three `not_sent` and carrying its
  // own reason. So *"No message is queued"* is not a guess about an open
  // question — it is what the server says after a real press.
  const msgs = built.manifest.messages;
  check("9 · the commit decided all three messages", msgs?.decided_count === 3, String(msgs?.decided_count));
  check(
    "9 · and QUEUED NONE of them — which is what step 8's second row says",
    msgs?.queued_count === 0,
    `queued_count=${msgs?.queued_count}, reasons: ${(msgs?.messages ?? []).map((m) => m.reason).join(", ")}`,
  );
  check("9 · the manifest carries a work-order count that the screen does NOT pre-empt",
    typeof built.manifest.work_orders === "number", String(built.manifest.work_orders));
  // ⚠ ASK THE QUEUE ITSELF. A commit that queued nothing still returns a dict.
  const queued = await api(`/api/${TENANT}/connections/${built.id}`);
  say("   the build's own record:", queued.body.slice(0, 300));
}

say(`\nscreenshots in ${OUT}`);
say(failures === 0 ? "ALL CHECKS PASSED" : `${failures} CHECK(S) FAILED`);
await browser.close();
process.exit(failures === 0 ? 0 : 1);
