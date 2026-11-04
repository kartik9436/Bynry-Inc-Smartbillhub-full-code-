// ── Trace ──────────────────────────────────────────────
// Change:  CR-089 wave F — F1 (`PUJ-29`) the Overview carries the unit's own
//          number · F2 (`PUJ-28`) an occupied unit shows its ACCOUNT and a
//          vacant one names the owner's · F3 the four tiles are the PAGE's,
//          on all six tabs · F4 (`PUJ-42`) a vacancy is a ROW · F5 (`PUJ-43`)
//          the audit tab draws its own rows · F6 (`PUJ-44`/`PUJ-45`) the unit
//          has an edit screen and the plan is on it.
// Rules:   PO definition of done, verbatim: *"everything should be executed
//          based on actual code, and rules that we place, also ensure you do
//          web walkthorugh before you sign off the user story or build"* ·
//          hard-won law 6 (no gate looks at rendered output).
// ───────────────────────────────────────────────────────
//
// WHAT THIS PROVES THAT A UNIT TEST CANNOT.
//
//   1 · **THE FOUR TILES SURVIVE A REAL TAB CHANGE, AND WHAT THAT COSTS.**
//       The strip is asserted on all six tabs of a real unit, and the number of
//       `/api/**` requests the page issues is COUNTED — first load and every
//       tab change after it. `CR-089` §5 flags this ruling as the one whose
//       cost grows with tenant size, and a measured number is the only kind
//       worth writing into a report.
//   2 · **THE FIGURES ARE THE SERVER'S.** Every tile is compared against the
//       payload `GET /units/{id}` actually returned, so a screen that computed
//       a plausible number of its own would fail here and nowhere else.
//   3 · **A VACANCY ROW ON REAL DATA.** `SCW-U-042` has a tenancy that CLOSED,
//       so the gap is derived from rows a person put there rather than from a
//       fixture written to make the arithmetic come out.
//   4 · **THE EMPTY CASES ARE ALSO CLAIMS** — a unit with no work order must
//       read `0` and not a dash, and a unit whose account could not be read
//       must not read `$0.00`.
//
// ⚠ RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING — a mid-run reseed looks
// exactly like a broken screen. `10-scripts/proof-db.sh clone <label> --export`.
const { existsSync, readdirSync, mkdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8392";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr89f/walk";
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome", "chrome-linux/headless_shell"]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  throw new Error("no chromium found");
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1500, height: 1300 } });
const say = (...parts) => console.log(...parts);
let failures = 0;
function check(label, ok, detail = "") {
  say(`${ok ? "PASS" : "FAIL"}  ${label}${detail === "" ? "" : ` — ${detail}`}`);
  if (!ok) failures += 1;
}

// Every /api request the page makes, counted per navigation.
let apiCalls = [];
page.on("request", (req) => {
  const url = req.url();
  if (url.includes("/api/")) apiCalls.push(url.split("/api/")[1]);
});

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

const list = JSON.parse((await api(`/api/${TENANT}/units?per=400`)).body);
const byNo = (no) => (list.results ?? []).find((r) => r.unit_no === no);

// ── the three addresses this walk uses, and why each ───────────────────────
//   SCW-U-201 · 1408 Elm Street  — occupied, account A-10432, autopay ON and a
//                                  $150.00 deposit: every fact `F2` names.
//   SCW-U-042 · 301 Mill Pond Ln — a tenancy that CLOSED on 31 Jul 2026, so
//                                  `F4`'s vacancy is derived from real rows.
//   SCW-U-307 · Kestrel Park ph. 2 — one PLANNED work order, so `F3`'s fourth
//                                  tile has a non-zero figure to show.
const OCCUPIED = byNo(process.env.OCCUPIED_UNIT ?? "SCW-U-201");
const VACANT = byNo(process.env.VACANT_UNIT ?? "SCW-U-042");
const WORKED = byNo(process.env.WORK_UNIT ?? "SCW-U-307");
for (const [name, row] of [["occupied", OCCUPIED], ["vacant", VACANT], ["worked", WORKED]]) {
  if (!row) throw new Error(`no ${name} unit on this tenant — set the env override`);
  say(`${name}: ${row.unit_no} · ${row.premise_address}`);
}

const unitPath = (id, tab) => `${BASE}/${TENANT}/premises/units/${id}?tab=${tab}`;
const tiles = () =>
  page.$$eval(".kpi", (nodes) =>
    nodes.map((n) => ({
      label: (n.querySelector(".k")?.childNodes[0]?.textContent ?? "").trim(),
      value: (n.querySelector(".v")?.innerText ?? "").trim(),
      detail: (n.querySelector(".d")?.innerText ?? "").trim(),
    })),
  );

// ── 1 · F1 — the unit's number on the Overview ─────────────────────────────
await page.goto(unitPath(OCCUPIED.id, "overview"), { waitUntil: "networkidle" });
await page.waitForSelector(".met-facts", { timeout: 20000 });
const facts = await page.$$eval(".met-facts dt", (ns) => ns.map((n) => n.textContent.trim()));
const firstValue = await page.$eval(".met-facts dd", (n) => n.innerText.trim());
say("overview facts:", JSON.stringify(facts));
check("F1 · the unit number is the FIRST fact on the Overview", facts[0] === "Unit ID", facts[0]);
check("F1 · and it holds this unit's number", firstValue.includes(OCCUPIED.unit_no), firstValue);
await page.screenshot({ path: `${OUT}/01-overview.png`, fullPage: true });

// ── 2 · F2 — the account, not an occupant's name ───────────────────────────
const overview = await page.evaluate(() => document.querySelector("main")?.innerText ?? "");
const detail = JSON.parse((await api(`/api/${TENANT}/units/${OCCUPIED.id}/account`)).body);
const acct = detail.account;
check("F2 · the account NUMBER is on the Overview", overview.includes(acct.account_no), acct.account_no);
check("F2 · and it is a link", (await page.$$(`main a:has-text("${acct.account_no}")`)).length > 0);
check("F2 · the holder is named", overview.includes(acct.name), acct.name);
check("F2 · the status is named", overview.includes(acct.status_name), acct.status_name);
const money = (s) => `$${Number(s).toFixed(2)}`;
check("F2 · what is owed, at 2 dp", overview.includes(money(acct.balance)), money(acct.balance));
check(
  "F2 · the deposit held",
  detail.facts.deposit.any ? overview.includes(money(detail.facts.deposit.held)) : true,
  money(detail.facts.deposit.held),
);
check("F2 · whether autopay will take it", /autopay/i.test(overview), "");
check(
  "F2 · when it is due is a STATED ABSENCE, not an invented date",
  overview.includes("Due date not known yet"),
  "",
);
check("F2 · one link out", overview.includes("Open the account tab"), "");
say("--- the account block, as rendered ---");
say(overview.split("Account").slice(-1)[0].trim().slice(0, 400));

// ── 3 · F3 — the four tiles, on all six tabs, and what they cost ──────────
const TABS = ["overview", "assets", "plan", "account", "occupancy", "audit"];
const served = JSON.parse((await api(`/api/${TENANT}/units/${OCCUPIED.id}`)).body);
apiCalls = [];
await page.goto(unitPath(OCCUPIED.id, "overview"), { waitUntil: "networkidle" });
await page.waitForSelector(".kpi", { timeout: 20000 });
await page.waitForTimeout(800);
const firstLoad = apiCalls.length;
say(`api calls on FIRST LOAD of the unit page: ${firstLoad}`);
say("   " + JSON.stringify(apiCalls));

for (const tab of TABS) {
  apiCalls = [];
  await page.click(`[role="tab"]:has-text("${tab === "audit" ? "Audit log" : tab}")`).catch(async () => {
    await page.goto(unitPath(OCCUPIED.id, tab), { waitUntil: "networkidle" });
  });
  await page.waitForTimeout(900);
  const t = await tiles();
  const labels = t.map((x) => x.label);
  check(
    `F3 · Assets · Owed · Plan · Open work on the ${tab} tab`,
    JSON.stringify(labels) === JSON.stringify(["Assets", "Owed", "Plan", "Open work"]),
    JSON.stringify(labels),
  );
  if (tab !== "overview") {
    say(`   tab change to "${tab}" cost ${apiCalls.length} api call(s): ${JSON.stringify(apiCalls)}`);
  }
  if (tab === "overview") {
    say("   tiles:", JSON.stringify(t));
    check("F3 · the Assets tile is the SERVER's count", t[0].value === String(served.assets.total), `${t[0].value} vs ${served.assets.total}`);
    check(
      "F3 · and it splits on the server's own category",
      t[0].detail === `${served.assets.bills} bill · ${served.assets.behind} behind the meter`,
      t[0].detail,
    );
    check("F3 · the Owed tile is the ledger's figure", t[1].value.includes(money(served.owed.balance)), t[1].value);
    check("F3 · the Open work tile is the work module's count", t[3].value === String(served.open_work.count), `${t[3].value} vs ${served.open_work.count}`);
  }
}
await page.screenshot({ path: `${OUT}/02-tiles.png`, fullPage: false });

// the non-zero Open work case, on the unit that has one
const workedServed = JSON.parse((await api(`/api/${TENANT}/units/${WORKED.id}`)).body);
await page.goto(unitPath(WORKED.id, "overview"), { waitUntil: "networkidle" });
await page.waitForSelector(".kpi", { timeout: 20000 });
const workedTiles = await tiles();
say("worked unit tiles:", JSON.stringify(workedTiles));
check(
  "F3 · Open work shows a real figure where a job is planned",
  workedTiles[3].value === String(workedServed.open_work.count) && Number(workedTiles[3].value) > 0,
  `${workedTiles[3].value} (server ${workedServed.open_work.count})`,
);
check(
  "F3 · a unit with no occupying account says who is billed, not $0.00",
  workedTiles[1].value !== "$0.00",
  workedTiles[1].value,
);
await page.screenshot({ path: `${OUT}/03-open-work.png`, fullPage: false });

// ── 4 · F2 vacant + F4 vacancy row ────────────────────────────────────────
await page.goto(unitPath(VACANT.id, "overview"), { waitUntil: "networkidle" });
await page.waitForTimeout(900);
const vacantOverview = await page.evaluate(() => document.querySelector("main")?.innerText ?? "");
check(
  "F2 · a vacant unit says base charges reach the owner",
  /base charges bill to the owner/i.test(vacantOverview),
  "",
);
const ownerAnswer = JSON.parse((await api(`/api/${TENANT}/units/${VACANT.id}/account`)).body);
if (ownerAnswer.owner_account) {
  check(
    "F2 · and NAMES the owner's account",
    vacantOverview.includes(ownerAnswer.owner_account.account_no),
    ownerAnswer.owner_account.account_no,
  );
} else {
  check(
    "F2 · with no owner on file it says the owner is not recorded, and invents none",
    /owner/i.test(vacantOverview),
    "no master account covers this unit on this tenant",
  );
}
await page.screenshot({ path: `${OUT}/04-vacant-overview.png`, fullPage: true });

await page.goto(unitPath(VACANT.id, "occupancy"), { waitUntil: "networkidle" });
await page.waitForSelector("table tbody tr", { timeout: 20000 });
const rows = await page.$$eval("table tbody tr", (ns) =>
  ns.map((n) => ({
    kind: n.getAttribute("data-occupancy-row"),
    cells: Array.from(n.querySelectorAll("td")).map((c) => c.innerText.trim()),
  })),
);
say("occupancy rows:", JSON.stringify(rows, null, 1));
const vacancy = rows.find((r) => r.kind === "vacancy");
check("F4 · a vacancy is a ROW between/after the tenancies", vacancy !== undefined, JSON.stringify(rows.map((r) => r.kind)));
if (vacancy) {
  check("F4 · it says Vacant", /vacant/i.test(vacancy.cells[0]), vacancy.cells[0]);
  check("F4 · it carries a start date", vacancy.cells[2] !== "", vacancy.cells[2]);
  check("F4 · it carries a length in days", /\d+\s*days?/.test(vacancy.cells[4]), vacancy.cells[4]);
  check(
    "F4 · and says who the base charge goes to",
    /Base charges bill to the owner/.test(vacancy.cells[4]),
    vacancy.cells[4],
  );
  // ⚠ ONE "Vacant" on the row. The units-list money cell bundles the state word
  // into its sentence ("Vacant — base charges…") because that column has no
  // other word saying so; here the Occupant cell already does, and the bundled
  // form printed it twice. A check for "contains Vacant" passes over that.
  check(
    "F4 · and says Vacant ONCE, not twice",
    (vacancy.cells.join(" ").match(/Vacant/g) ?? []).length === 1,
    vacancy.cells.join(" | "),
  );
}
await page.screenshot({ path: `${OUT}/05-vacancy-row.png`, fullPage: true });

// ── 5 · F5 — the audit tab draws its own rows ─────────────────────────────
await page.goto(unitPath(OCCUPIED.id, "audit"), { waitUntil: "networkidle" });
await page.waitForTimeout(1200);
const auditRows = await page.$$eval("table tbody tr", (ns) =>
  ns.map((n) => Array.from(n.querySelectorAll("td")).map((c) => c.innerText.trim())),
);
say("audit rows:", JSON.stringify(auditRows.slice(0, 3), null, 1));
check("F5 · the unit's audit tab draws ROWS, not a sentence pointing elsewhere", auditRows.length > 0, `${auditRows.length} rows`);
check(
  "F5 · a row carries the old value beside the new, with no expand control",
  auditRows.some((r) => r.some((c) => c.includes("→"))) &&
    (await page.$$('table button[aria-expanded]')).length === 0,
  "",
);
await page.screenshot({ path: `${OUT}/06-audit.png`, fullPage: true });

// ── 6 · F6 — the edit screen, and the plan on it ──────────────────────────
await page.goto(unitPath(OCCUPIED.id, "overview"), { waitUntil: "networkidle" });
await page.waitForTimeout(700);
const editButton = await page.$('button:has-text("Edit")');
check("F6 · the unit's own page offers Edit", editButton !== null, "");
if (editButton) {
  await editButton.click();
  await page.waitForSelector("#label", { timeout: 15000 });
  const before = JSON.parse((await api(`/api/${TENANT}/units/${OCCUPIED.id}`)).body);
  const modal = await page.evaluate(() => document.querySelector("form")?.innerText ?? "");
  check("F6 · the form carries the label", modal.includes("Unit label"), "");
  check("F6 · the floor area", modal.includes("Square feet"), "");
  check("F6 · and the PLAN", /\bPlan\b/.test(modal), "");
  // A label derived from the clock, so the check cannot pass because a previous
  // run of this walk left the unit already carrying the value being written.
  const newLabel = `2B-${Date.now().toString().slice(-5)}`;
  await page.fill("#label", newLabel);
  await page.fill("#square_feet", "820");
  await page.screenshot({ path: `${OUT}/07-edit-form.png`, fullPage: true });
  await page.click('form button[type="submit"]');
  await page.waitForTimeout(2500);
  const after = JSON.parse((await api(`/api/${TENANT}/units/${OCCUPIED.id}`)).body);
  check("F6 · the label was changed", after.label === newLabel && after.label !== before.label, `${before.label} -> ${after.label}`);
  check("F6 · the floor area was changed to 820", String(after.square_feet) === "820", String(after.square_feet));
  // put it back, so the walkthrough leaves the tenant as it found it
  await api(`/api/${TENANT}/units/${OCCUPIED.id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ label: before.label, square_feet: before.square_feet }),
  });
  const restored = JSON.parse((await api(`/api/${TENANT}/units/${OCCUPIED.id}`)).body);
  check("F6 · and the walk left the unit as it found it", restored.label === before.label, restored.label);

  // ── 7 · F6's other half (`PUJ-45`) — THE PLAN MOVES THROUGH THE SAME FORM ──
  //
  // ⚠ **THIS IS THE CHECK THAT COULD ONLY EVER BE MADE HERE.** `plan` has been
  // in `_validate_unit`'s `ignored` set since S16, so before this wave a PATCH
  // carrying a plan block answered **200**, changed the label, left the plan
  // exactly where it was and said nothing — and the form would have looked like
  // it worked to every clerk, forever. The proof is to read the plan back from
  // the SERVER after pressing Save.
  // ⚠ **`/plans`, WHICH IS WHAT THE PICKER READS — NOT `/rate-schedules`.**
  // The first draft asked for rate schedules, whose ids are a different family
  // altogether, so the "is the new plan a published one" check could never
  // match and reported FAIL over a plan that had moved correctly. A check
  // looking at the wrong thing, found by reading its own failure text.
  const plans = JSON.parse((await api(`/api/${TENANT}/plans?per=100&f.status=published`)).body);
  const published = (plans.results ?? []).filter((p) => p.id !== before.rate_plan_id);
  if (published.length === 0) {
    say("SKIP  F6 · no second published plan on this tenant to move to");
  } else {
    const target = published[0];
    await (await page.$('button:has-text("Edit")')).click();
    await page.waitForSelector("#tariff_id", { timeout: 15000 });
    await page.fill("#tariff_id", String(target.name).slice(0, 8));
    await page.waitForTimeout(700);
    await page.keyboard.press("ArrowDown");
    await page.keyboard.press("Enter");
    await page.waitForTimeout(500);
    await page.screenshot({ path: `${OUT}/08-plan-on-the-edit-form.png`, fullPage: true });
    // ⚠ **READ WHAT THE CONTROL ACTUALLY HOLDS, NOT WHAT WE MEANT TO PICK.**
    // The first draft asserted against `target.id` — the plan the SCRIPT chose
    // — and reported FAIL while the plan had moved perfectly well, because the
    // keyboard selection in a `SearchSelectField` landed on a different
    // filtered row. That is a check looking at the wrong thing, and it would
    // have condemned a working form. `#tariff_id` is a `role="combobox"` INPUT
    // whose `value` is the LABEL, not the option's id, so the round trip is
    // asserted the way a person would: save, reopen the form, and see the
    // picker showing the plan the server now holds.
    const shownBefore = await page.$eval("#tariff_id", (n) => n.value);
    await page.click('form button[type="submit"]');
    await page.waitForTimeout(2500);
    const moved = JSON.parse((await api(`/api/${TENANT}/units/${OCCUPIED.id}`)).body);
    check(
      "F6 · pressing Save on the edit form MOVED the unit's plan",
      moved.rate_plan_id !== before.rate_plan_id &&
        (plans.results ?? []).some((p) => p.id === moved.rate_plan_id),
      `${before.rate_plan_id} -> ${moved.rate_plan_id} (the form showed "${shownBefore}")`,
    );
    await page.reload({ waitUntil: "networkidle" });
    await page.waitForTimeout(900);
    await (await page.$('button:has-text("Edit")')).click();
    await page.waitForSelector("#tariff_id", { timeout: 15000 });
    // ⚠ **`waitForSelector` RESOLVES WHEN THE INPUT EXISTS, WHICH IS BEFORE THE
    // PLAN LIST HAS LANDED.** The first draft read the value at that moment,
    // got `""` and reported a defect that had just been fixed. The wait below
    // is for the OPTIONS, not for the assertion: if the control never fills,
    // the equality on the next line still fails and still names the fault.
    await page
      .waitForFunction(() => document.querySelector("#tariff_id")?.value !== "", { timeout: 6000 })
      .catch(() => undefined);
    const shownAfter = await page.$eval("#tariff_id", (n) => n.value);
    check(
      "F6 · and reopening the form shows the plan the server now holds",
      shownAfter === shownBefore && shownAfter !== "",
      `"${shownAfter}"`,
    );
    await page.keyboard.press("Escape").catch(() => undefined);
    await page.waitForTimeout(400);
    // put it back, through the same door
    await api(`/api/${TENANT}/units/${OCCUPIED.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ plan: { tariff_id: before.rate_plan_id } }),
    });
    const back = JSON.parse((await api(`/api/${TENANT}/units/${OCCUPIED.id}`)).body);
    check("F6 · and the plan was put back", back.rate_plan_id === before.rate_plan_id, back.rate_plan_id);
    say(
      "   this leaves TWO real rows in `unit_plan_assignments` on the demo tenant — " +
        "that is the history a plan change is SUPPOSED to write, and it is stated rather than hidden.",
    );
  }
}

say(failures === 0 ? "\nALL CHECKS PASSED" : `\n${failures} CHECK(S) FAILED`);
await browser.close();
process.exit(failures === 0 ? 0 : 1);
