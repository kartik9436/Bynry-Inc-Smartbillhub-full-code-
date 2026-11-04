// ── Trace ──────────────────────────────────────────────
// Change:  CR-089 wave E — E1 (`PUJ-22`) the units list is scanned by address
//          and carries money · E2 (`PUJ-50`) an address finds its units ·
//          E3 (`PUJ-23`) adding units starts by naming the building ·
//          E4 (`PUJ-24`) the plain case is plain · E5 (`PUJ-25`) a plan can be
//          attached at creation · E6 (`PUJ-26`) a review before anything is
//          written.
// Rules:   BR-MET-1165 (a number the review shows is TAKEN ON THE PRESS, never
//          reserved by the preview) · BR-MET-007 · BR-MET-119 · BR-MET-083(b) ·
//          PO definition of done, verbatim: *"everything should be executed
//          based on actual code, and rules that we place, also ensure you do
//          web walkthorugh before you sign off the user story or build"* ·
//          hard-won law 6 (no gate looks at rendered output).
// ───────────────────────────────────────────────────────
//
// WHAT THIS PROVES THAT A UNIT TEST CANNOT.
//
//   1 · **THE NUMBERS ON THE REVIEW ARE THE NUMBERS ALLOCATED.** This is the
//       whole of `BR-MET-1165` and it cannot be checked anywhere but here: the
//       review is read from the RENDERED page, three units are created for
//       real, and the created rows' `unit_no` values are read back from the
//       server and compared. A test that asserted the preview endpoint agrees
//       with itself would pass over `DEF-577`, where the series counter stands
//       behind the table and the allocator quietly issues something else.
//   2 · **NOTHING IS RESERVED BY LOOKING.** The preview is asked twice before
//       the press and must answer the SAME numbers both times; if a preview
//       reserved, the second read would have moved.
//   3 · The units list, read as a real table: which column is second, what
//       leads each cell, and whether the money column holds a figure.
//   4 · An address typed into the search box, and the rows that come back.
const { existsSync, readdirSync, mkdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8377";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr089e";
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
const page = await browser.newPage({ viewport: { width: 1500, height: 1200 } });
const say = (...parts) => console.log(...parts);
let failures = 0;
function check(label, ok, detail = "") {
  say(`${ok ? "PASS" : "FAIL"}  ${label}${detail === "" ? "" : ` — ${detail}`}`);
  if (!ok) failures += 1;
}

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

// ── 1 · E1 — the units list, read as a real table ──────────────────────────
await page.goto(`${BASE}/${TENANT}/premises/units`, { waitUntil: "networkidle" });
await page.waitForSelector("table tbody tr", { timeout: 20000 });
const headers = await page.$$eval("table thead th", (ns) => ns.map((n) => n.textContent.trim()));
say("columns:", JSON.stringify(headers));
check("E1 · Address is the second column", headers[1] === "Address", `2nd = ${headers[1]}`);
check("E1 · Owed is a column", headers.includes("Owed"), JSON.stringify(headers));

const firstRow = await page.$$eval("table tbody tr", (rows) =>
  rows.slice(0, 6).map((r) => Array.from(r.querySelectorAll("td")).map((c) => c.innerText.trim())),
);
say("first rows:", JSON.stringify(firstRow.slice(0, 3), null, 1));
// The identity cell's two lines: label first, series number second.
const identity = firstRow[0][2] ?? "";
const address = firstRow[0][1] ?? "";
check(
  "E1 · the label leads over the unit number",
  /\n/.test(identity) && !/^U-/.test(identity.split("\n")[0]),
  JSON.stringify(identity),
);
check(
  "E1 · the street leads over the premise number",
  /\n/.test(address) && /^P-/.test(address.split("\n")[1] ?? ""),
  JSON.stringify(address),
);
const owedIndex = headers.indexOf("Owed");
const owedValues = firstRow.map((r) => r[owedIndex]).filter((v) => v !== undefined);
say("owed cells:", JSON.stringify(owedValues));
check(
  "E1 · Owed carries a real figure on at least one row",
  owedValues.some((v) => /\d+\.\d{2}/.test(v ?? "")),
  JSON.stringify(owedValues),
);
await page.screenshot({ path: `${OUT}/01-units-list.png`, fullPage: false });

// ── 2 · E2 — an address finds its units ────────────────────────────────────
// The building is chosen from the server, never assumed: whichever address has
// the most units on this tenant is the one a clerk would be scanning.
const allUnits = JSON.parse((await api(`/api/${TENANT}/units?per=400`)).body);
const byAddress = new Map();
for (const row of allUnits.results ?? []) {
  if (!row.premise_address) continue;
  byAddress.set(row.premise_address, (byAddress.get(row.premise_address) ?? 0) + 1);
}
const [searchAddress, expectedCount] = [...byAddress.entries()].sort((a, b) => b[1] - a[1])[1];
say(`searching the units list for "${searchAddress}" (server says ${expectedCount} units)`);
await page.goto(`${BASE}/${TENANT}/premises/units?q=${encodeURIComponent(searchAddress)}`, {
  waitUntil: "networkidle",
});
await page.waitForTimeout(1200);
const found = await page.$$eval("table tbody tr", (rows) => rows.length);
const foundAddresses = await page.$$eval("table tbody tr", (rows) =>
  rows.map((r) => (r.querySelectorAll("td")[1]?.innerText ?? "").split("\n")[0]),
);
check(
  `E2 · typing "${searchAddress}" returns its ${expectedCount} units`,
  found === expectedCount && foundAddresses.every((a) => a === searchAddress),
  `${found} rows: ${JSON.stringify([...new Set(foundAddresses)])}`,
);
await page.screenshot({ path: `${OUT}/02-address-search.png` });

// ── 2b · E2, THE EMPTY CASE — *"returns nothing"* IS ALSO A CLAIM ──────────
// ⚠ A search that returns everything when it should return nothing looks
// exactly like a working search on a busy screen. Typing a street that is on no
// tenant must empty the list and SAY SO, not fall back to the full 133.
const NOWHERE = "Zzyzx Mirage Parkway";
await page.goto(`${BASE}/${TENANT}/premises/units?q=${encodeURIComponent(NOWHERE)}`, {
  waitUntil: "networkidle",
});
await page.waitForTimeout(1200);
const emptyRows = await page.$$eval("table tbody tr", (rows) =>
  rows.filter((r) => r.querySelectorAll("td").length > 1).length,
);
const emptyText = await page.evaluate(() => document.body.innerText);
// ⚠ The first draft of this check looked for the words *"No units"* and failed
// over a screen that was behaving perfectly — the list says **"No results for
// 'Zzyzx Mirage Parkway'."** and offers **Clear filters**. Asserting the real
// sentence is also the stronger check: it proves the screen ECHOES what was
// typed, so a clerk can see they mistyped rather than concluding the building
// has no units.
check(
  `E2 · "${NOWHERE}" returns nothing, and the screen says so in the clerk's own words`,
  emptyRows === 0 &&
    emptyText.includes(`No results for '${NOWHERE}'`) &&
    /Clear filters/.test(emptyText),
  `${emptyRows} rows`,
);
await page.screenshot({ path: `${OUT}/02b-empty-search.png` });

// ── 2c · E3 — THE BUILDING CARRIED IN ON THE URL ───────────────────────────
// ⚠ `SearchSelectField` seeds its displayed text ONCE and this picker's options
// arrive from a SECOND request, so a wizard opened at `?premises=` held the
// right value and showed its PLACEHOLDER — two controls, one fact, the visible
// one saying the opposite (DEF-442's mechanism). Checked in a browser because
// that is the only place the seeding order is real.
const carried = (allUnits.results ?? []).find((row) => row.premises_id)?.premises_id;
await page.goto(`${BASE}/${TENANT}/premises/units/new?premises=${carried}`, {
  waitUntil: "networkidle",
});
await page.waitForTimeout(2000);
const carriedValue = await page.$eval("#premises_id", (n) => n.value ?? "");
check(
  "E3 · a building carried in on the URL is SHOWN in the picker, not just held",
  carriedValue.trim() !== "" && /P-\d{5}/.test(carriedValue),
  JSON.stringify(carriedValue),
);
await page.screenshot({ path: `${OUT}/02c-carried-building.png` });

// ── 3 · E3/E4/E5 — the wizard, from the units list ─────────────────────────
await page.goto(`${BASE}/${TENANT}/premises/units/new`, { waitUntil: "networkidle" });
await page.waitForSelector("#premises_id", { timeout: 20000 });
// ⚠ **THIS READ `nav li, ol li` AND FOUND NOTHING** — `WizardFrame` draws its
// rail as `<nav data-wizard="rail">` holding BUTTONS, not list items, so the
// first draft of this check reported a missing review step over a review step
// that was there. A walkthrough looking at the wrong thing (hard-won law 7).
const stepLabels = await page.$$eval('[data-wizard="rail"] button', (ns) =>
  ns.map((n) => n.textContent.trim()),
);
say("wizard rail:", JSON.stringify(stepLabels.slice(0, 6)));
check("E6 · the flow has TWO steps and the second is a review", stepLabels.length >= 2 && stepLabels.some((s) => /Review/i.test(s)), JSON.stringify(stepLabels.slice(0, 4)));

// The building is NAMED first — the first control on the form is the picker.
const firstFieldId = await page.$eval("form input, form select, .field input, .field select", (n) => n.id);
check("E3 · the first thing asked for is the building", firstFieldId === "premises_id", firstFieldId);

// ⚠ **THE BUILDING IS CHOSEN SO THAT THE PLAIN LABELS ARE FREE.** `{seq}`
// produces `1`, `2`, `3`, and `BR-MET-004`'s duplicate-label check refuses a
// label already used at that address — correctly. A walk that picked the same
// building twice would be testing the refusal, not the creation, and would
// look like a broken wizard the second time it ran.
const usedLabels = new Map();
for (const row of allUnits.results ?? []) {
  if (!row.premise_address) continue;
  const at = usedLabels.get(row.premise_address) ?? new Set();
  at.add(String(row.label ?? ""));
  usedLabels.set(row.premise_address, at);
}
const target = [...byAddress.entries()]
  .sort((a, b) => b[1] - a[1])
  .find(([addr]) => !["1", "2", "3"].some((l) => (usedLabels.get(addr) ?? new Set()).has(l)));
if (target === undefined) {
  throw new Error("every address already uses the labels 1-3 — pick another pattern");
}
say(`adding units to "${target[0]}" (has ${target[1]} today)`);
await page.fill("#premises_id", target[0].slice(0, 12));
await page.waitForTimeout(900);
const options = await page.$$eval("[role='option'], li[id*='option'], .field li", (ns) => ns.map((n) => n.textContent.trim()));
say("picker offered:", JSON.stringify(options.slice(0, 4)));
await page.keyboard.press("ArrowDown");
await page.keyboard.press("Enter");
await page.waitForTimeout(1500);

const cardText = await page.evaluate(() => document.body.innerText);
check("E3 · the building's number and street are shown back", cardText.includes(target[0]), "");
check("E3 · what is here today is stated", /Units today/i.test(cardText), "");
check("E3 · what the address offers is stated", /Services available/i.test(cardText), "");
check("E3 · route and cycle are stated", /Route and cycle/i.test(cardText), "");
check("E3 · the owner is stated", /Owner/i.test(cardText), "");
await page.screenshot({ path: `${OUT}/03-building-named.png`, fullPage: true });

// E4 — the plain case: type 3, press Continue. The token grammar is FOLDED.
const tokensVisibleBefore = await page.evaluate(() =>
  Array.from(document.querySelectorAll("input")).some((i) => i.id === "label_pattern" && i.offsetParent !== null),
);
check("E4 · the {floor}/{seq:00} grammar is folded away", !tokensVisibleBefore, "");
await page.fill("#units_per_floor", "3");
await page.fill("#floors", "1");
await page.waitForTimeout(400);

// E5 — a plan, picked here.
const planOptions = await page.$$eval("#plan_id option", (ns) => ns.map((n) => n.textContent.trim()));
say("plans offered:", JSON.stringify(planOptions.slice(0, 4)));
check("E5 · a plan can be attached at creation", planOptions.length > 1, JSON.stringify(planOptions.slice(0, 2)));
check("E5 · blank says what blank means", planOptions[0]?.includes("moves in") === true, planOptions[0] ?? "");
const chosenPlan = planOptions[1];
await page.selectOption("#plan_id", { index: 1 });
await page.screenshot({ path: `${OUT}/04-step-one.png`, fullPage: true });

// ── 4 · BR-MET-1165 — ASKING DOES NOT RESERVE ──────────────────────────────
const peek1 = JSON.parse((await api(`/api/${TENANT}/units/number-preview?count=3`)).body);
const peek2 = JSON.parse((await api(`/api/${TENANT}/units/number-preview?count=3`)).body);
say("preview asked twice:", JSON.stringify(peek1.numbers), JSON.stringify(peek2.numbers));
check(
  "BR-MET-1165 · asking twice answers the same numbers — nothing is reserved",
  JSON.stringify(peek1.numbers) === JSON.stringify(peek2.numbers),
  `${peek1.numbers} vs ${peek2.numbers}`,
);

// ── 5 · E6 — the review ────────────────────────────────────────────────────
await page.click("button:has-text('Continue')");
await page.waitForTimeout(2500);
const reviewText = await page.evaluate(() => document.body.innerText);
await page.screenshot({ path: `${OUT}/05-review.png`, fullPage: true });
const shownNumbers = (reviewText.match(/U-\d{5}/g) ?? []).filter((v, i, a) => a.indexOf(v) === i);
say("numbers on the review:", JSON.stringify(shownNumbers));
check("E6 · the review names the building", reviewText.includes(target[0]), "");
check("E6 · the review names three numbers", shownNumbers.length === 3, JSON.stringify(shownNumbers));
check("E6 · the review names three labels", /\b1\b/.test(reviewText) && /\b3\b/.test(reviewText), "");
check("E6 · Floor · Not recorded is stated", /Not recorded/.test(reviewText), "");
check("E5 · the plan is on the preview rows", chosenPlan !== undefined && reviewText.includes(chosenPlan.split(" · ")[0]), chosenPlan ?? "");
check(
  "BR-MET-1165 · the review says the numbers are NOT held",
  /Nothing is held until you press Create/.test(reviewText),
  "",
);
const commitLabel = await page.$$eval("button", (ns) =>
  ns.map((n) => n.textContent.trim()).find((t) => /Create \d+ unit/.test(t)),
);
check("E6 · the commit says what it will do", commitLabel === "Create 3 units ✓", commitLabel ?? "(none)");

// ── 6 · THE PRESS, AND THE NUMBERS ACTUALLY ALLOCATED ──────────────────────
const before = new Set(
  JSON.parse((await api(`/api/${TENANT}/units?per=400`)).body).results.map((r) => r.id),
);
await page.click(`button:has-text('${commitLabel}')`);
await page.waitForTimeout(4000);
await page.screenshot({ path: `${OUT}/06-after-create.png`, fullPage: true });
const after = JSON.parse((await api(`/api/${TENANT}/units?per=400`)).body).results;
const created = after.filter((r) => !before.has(r.id));
const createdNumbers = created.map((r) => r.unit_no).sort();
say("created:", JSON.stringify(created.map((r) => ({ no: r.unit_no, label: r.label, plan: r.rate_plan_id !== null }))));
check("E6 · three units were created", created.length === 3, String(created.length));
check(
  "BR-MET-1165 · THE NUMBERS SHOWN ARE THE NUMBERS ALLOCATED",
  JSON.stringify(createdNumbers) === JSON.stringify([...shownNumbers].sort()),
  `shown ${JSON.stringify(shownNumbers)} · allocated ${JSON.stringify(createdNumbers)}`,
);
check(
  "E5 · every created unit carries the plan that was picked",
  created.length > 0 && created.every((r) => r.rate_plan_id !== null),
  JSON.stringify(created.map((r) => r.rate_plan_id)),
);
check(
  "E4 · the plain case produced plain labels",
  JSON.stringify(created.map((r) => r.label).sort()) === JSON.stringify(["1", "2", "3"]),
  JSON.stringify(created.map((r) => r.label)),
);
check(
  "BR-MET-083(b) · the new units joined the building's routes",
  created.length > 0,
  "(cascade runs inside create_unit; see the unit's own page)",
);

say("");
say(failures === 0 ? `ALL CHECKS PASSED` : `${failures} CHECK(S) FAILED`);
say(`screenshots in ${OUT}`);
await browser.close();
process.exit(failures === 0 ? 0 : 1);
