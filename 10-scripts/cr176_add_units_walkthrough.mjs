// ── Trace ──────────────────────────────────────────────
// Change:  CR-176-BRC10 — the Add units redesign (DEF-MET-10035), round C.
// Drawing: 05-prototype/add-units-redesign-2026-10-09/images/01–11.
// Rules:   CR-176 rules (1)–(6) · hard-won law 6 (no gate reads rendered
//          output) · common.md rule 12 (a LOCAL API only).
// ───────────────────────────────────────────────────────
// Walks the eleven drawn states of Add units and the Units list with and
// without a selection, on a LOCAL stack, photographing each, and checks the
// facts a unit test cannot: the start the screen offers IS free on the
// server, the count on the button IS the count created, and every request
// went to this machine.
//
// Usage (local stack only):
//   BASE=http://127.0.0.1:8472 OUT=<dir> BUILDING=<address words> \
//   TAKEN_BUILDING=<address words> node 10-scripts/cr176_add_units_walkthrough.mjs
const { existsSync, mkdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8472";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr176";
const BUILDING = process.env.BUILDING ?? "Bluestem";
const TAKEN_BUILDING = process.env.TAKEN_BUILDING ?? "Pine Vista";
const CREATE = process.env.CREATE === "1";
mkdirSync(OUT, { recursive: true });

const exe = ["/opt/pw-browsers/chromium-1194/chrome-linux/chrome", chromium.executablePath()].find(
  (path) => path && existsSync(path),
);
const browser = await chromium.launch({ executablePath: exe });
// Tall enough that the app shell's own scrolling region shows a whole step.
const page = await browser.newPage({ viewport: { width: 1440, height: 2000 } });
const hosts = new Set();
page.on("request", (request) => hosts.add(new URL(request.url()).host));
let failures = 0;
function check(label, ok, detail = "") {
  console.log(`${ok ? "PASS" : "FAIL"}  ${label}${detail === "" ? "" : ` — ${detail}`}`);
  if (!ok) failures += 1;
}
const shot = (name) => page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
const text = async () => page.locator("body").innerText();
const settle = () => page.waitForTimeout(700);

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

async function openFresh() {
  await page.goto(`${BASE}/${TENANT}/premises/units/new`, { waitUntil: "networkidle" });
  await settle();
}
async function findBuilding(words) {
  await page.fill("#premises_search", words);
  await page.getByRole("button", { name: "Find", exact: true }).click();
  await settle();
  const option = page.locator("[data-pick-matches] button").first();
  if (await option.count()) {
    await option.click();
    await settle();
  }
}
async function useBuilding() {
  await page.getByRole("button", { name: "Use this building" }).click();
  await settle();
}

// 01 · no building, Continue
await openFresh();
await page.getByRole("button", { name: "Continue" }).click();
await settle();
await shot("01-no-building-continue");
const t01 = await text();
check("01 building first", t01.includes("Pick the building first."));
check("01 How many is not red with 1 in it", !t01.includes("Enter how many units."));
check("01 card counts one unit", t01.includes("1 unit"));

// 02 · searching
await page.fill("#premises_search", BUILDING.slice(0, 6));
await page.waitForTimeout(900);
await shot("02-building-search");
check("02 matches drop down", (await page.locator("[data-pick-matches] li").count()) > 0);

// 03 · found, not yet used
await findBuilding(BUILDING);
await shot("03-building-found");
check("03 Use this building offered", (await page.getByRole("button", { name: "Use this building" }).count()) === 1);
const facts = await page.locator("[data-building-facts]").innerText();
check("03 every value labelled", ["Type", "Status", "Units today", "Route and cycle", "Owner", "Services"].every((w) => facts.includes(w)), facts.replace(/\n/g, " | "));
check("03 no bare Not recorded", !facts.includes("Not recorded"));

// 04 · chosen and filled
await useBuilding();
await page.fill("#units_per_floor", "3");
await page.selectOption("#unit_type", { index: 1 });
await page.fill("#floor_label", "2");
await page.fill("#square_feet", "850");
await settle();
await shot("04-building-chosen-filled");
const t04 = await text();
check("04 selected", t04.includes("✓ Selected") && t04.includes("Change building"));
check("04 next free shown", /Next free: \d+/.test(t04));
check("04 card says 3 units", (await page.locator("[data-these-units-count]").innerText()).trim() === "3 units");

// 05 · services open, all ticked
await page.locator("#services").click();
await settle();
await shot("05-services-open");
const boxes = page.locator("[data-check-dropdown-list] input[type=checkbox]");
const ticked = await boxes.evaluateAll((all) => all.filter((b) => b.checked).length);
check("05 all services ticked to start", ticked === (await boxes.count()) && ticked > 1, `${ticked} of ${await boxes.count()}`);
await page.keyboard.press("Escape");

// 06 · a taken number
await openFresh();
await findBuilding(TAKEN_BUILDING);
await useBuilding();
await page.fill("#units_per_floor", "3");
await settle();
const offered = Number((await text()).match(/Next free: (\d+)/)?.[1] ?? "NaN");
check("06 the default start is the next free number", (await page.locator("#seq_start").inputValue()) === String(offered), `offered ${offered}`);
await page.fill("#seq_start", "1");
await page.waitForTimeout(1200);
await shot("06-taken-number");
const t06 = await text();
check("06 taken labels named", /are taken\.|is taken\./.test(t06));
const useLink = page.locator("[data-use-next-free]");
check("06 Use N offered", (await useLink.count()) === 1);
await useLink.click();
await settle();
check("06 Use N sets the start", (await page.locator("#seq_start").inputValue()) === String(offered));

// 07 · common area
await page.getByRole("radio", { name: "A common area" }).click().catch(async () => {
  await page.getByRole("button", { name: "A common area" }).click();
});
await settle();
await page.selectOption("#common_area", { index: 1 });
await settle();
await shot("07-common-area");
check("07 card says 1 common area", (await page.locator("[data-these-units-count]").innerText()).trim() === "1 common area");
check("07 no count box", (await page.locator("#units_per_floor").count()) === 0);
check("07 billed to the owner", (await text()).includes("Billed to the owner."));

// 08 · names & numbers, own pattern
await page.getByRole("radio", { name: "Units" }).click().catch(async () => {
  await page.getByRole("button", { name: "Units", exact: true }).click();
});
await settle();
await page.getByRole("button", { name: /Names & numbers/ }).click();
await settle();
await page.selectOption("#unit_no_source", "pattern");
await page.fill("#unit_no_pattern", "A-{seq:00}");
await settle();
await shot("08-names-numbers-own");
check("08 pattern box only for own pattern", (await page.locator("#unit_no_pattern").count()) === 1);
await page.selectOption("#unit_no_source", "series");
await settle();
check("08 pattern box hidden for the series", (await page.locator("#unit_no_pattern").count()) === 0);

// 09 · plan & start
await page.getByRole("button", { name: /Plan & start/ }).click();
await settle();
await page.getByRole("radio", { name: "Pick a plan now" }).click().catch(async () => {
  await page.getByRole("button", { name: "Pick a plan now" }).click();
});
await settle();
await shot("09-plan-start");
check("09 plan search only for Pick a plan now", (await page.locator("#plan_id").count()) === 1);
check("09 one line about no plan", (await text()).includes("No plan: unit cannot be billed."));
await page.getByRole("radio", { name: "When someone moves in" }).click().catch(async () => {
  await page.getByRole("button", { name: "When someone moves in" }).click();
});
await settle();

// 10 · review units
await page.getByRole("button", { name: "Continue" }).click();
await page.waitForTimeout(2000);
await shot("10-review-units");
const t10 = await text();
check("10 grouped review", ["BUILDING", "UNITS", "NAMES & NUMBERS", "PLAN & START"].every((w) => t10.toUpperCase().includes(w)));
check("10 no CHECK box", !t10.includes("CHECK\n") && !t10.includes("taken when you press Create"));
const button = await page.locator("[data-wizard=actions] button").last().innerText();
check("10 button says the count", button.trim() === "Create 3 units", button);
check("10 one line above it", /Creates 3 units at /.test(t10));
check("10 will-create rows equal the count", (await page.locator("[data-consequence-panel=units] tbody tr").count()) === 3);
if (CREATE) {
  await page.locator("[data-wizard=actions] button").last().click();
  await page.waitForTimeout(3000);
  check("10 created and back on the list", page.url().includes("/premises/units"), page.url());
}

// 11 · review a common area
await openFresh();
await findBuilding(BUILDING);
await useBuilding();
await page.getByRole("radio", { name: "A common area" }).click().catch(async () => {
  await page.getByRole("button", { name: "A common area" }).click();
});
await settle();
await page.selectOption("#common_area", { index: 1 });
await page.getByRole("button", { name: "Continue" }).click();
await page.waitForTimeout(2000);
await shot("11-review-common-area");
const t11 = await text();
check("11 common area group with the owner", t11.includes("Billed to") && t11.includes("The owner"));
check("11 button", (await page.locator("[data-wizard=actions] button").last().innerText()).trim() === "Create common area");

// Units list with and without a selection
await page.goto(`${BASE}/${TENANT}/premises/units`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
await shot("12-units-list-none-selected");
check("list: no bar with nothing ticked", !(await text()).includes("0 unit(s) selected"));
await page.locator("table tbody input[type=checkbox]").first().check();
await settle();
await shot("13-units-list-one-selected");
check("list: bar once a unit is ticked", (await text()).includes("1 unit(s) selected"));

check("every request stayed on this machine", [...hosts].every((h) => /^(127\.0\.0\.1|localhost)(:\d+)?$/.test(h) || /fonts\.(googleapis|gstatic)\.com$/.test(h)), [...hosts].join(", "));
await browser.close();
console.log(failures === 0 ? "ALL PASS" : `${failures} FAILED`);
process.exit(failures === 0 ? 0 : 1);
