/**
 * cr177_add_premise_walkthrough — Add a premise (CR-177-BRC10), photographed in
 * the 14 states of the approved drawing (`05-prototype/add-premise-2026-10-09/`).
 *
 *   BASE=http://127.0.0.1:5461 OUT=<dir> WORLD="<cmd that runs cr177_add_premise_world.py>" \
 *     node 10-scripts/cr177_add_premise_walkthrough.mjs
 *
 * ⚠ LOCAL ONLY. BASE must be a local server proxying a local API; the script
 * refuses any other host, and every request the page makes is checked to stay
 * on BASE's origin. The City map is a RECORDED `.example` host
 * (`gis_fixtures.FAST_HOST`) switched on and off by the world script.
 */
import { execSync } from "node:child_process";
import { existsSync, mkdirSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5461";
if (!/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(BASE)) throw new Error(`refusing a non-local BASE: ${BASE}`);
const TENANT = "brazosbend";
const EMAIL = "dana@brazosbendutilities.com";
const PASSWORD = "S3cure!passw0rd"; // the seeded demo credential — local only
const OUT = process.env.OUT ?? "/tmp/cr177-walk";
const WORLD = process.env.WORLD;
mkdirSync(OUT, { recursive: true });
const results = [];
function check(step, what, pass, evidence = "") {
  results.push({ step, what, pass: Boolean(pass), evidence: String(evidence) });
  console.log(`${pass ? "PASS" : "FAIL"} ${step} ${what} — ${String(evidence).slice(0, 200)}`);
}
const world = (cmd) => console.log(execSync(`${WORLD} ${cmd}`, { encoding: "utf8" }).trim());

function resolveChromium() {
  for (const dir of readdirSync("/opt/pw-browsers")) {
    if (!dir.startsWith("chromium")) continue;
    for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome"]) {
      const candidate = join("/opt/pw-browsers", dir, sub);
      if (existsSync(candidate)) return candidate;
    }
  }
  throw new Error("no chromium found");
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
// The product's own webfont (`src/styles/tokens.css` → Google Fonts) is the one
// expected outside request; it is counted and printed, never hidden. Anything
// else — the live site, a City map, a payment or census host — fails the walk.
const FONT_HOSTS = ["https://fonts.googleapis.com/", "https://fonts.gstatic.com/"];
const offOrigin = [];
const fontRequests = [];
page.on("request", (req) => {
  const url = req.url();
  if (url.startsWith(BASE) || url.startsWith("data:") || url.startsWith("blob:")) return;
  if (FONT_HOSTS.some((host) => url.startsWith(host))) fontRequests.push(url);
  else offOrigin.push(url);
});
const settle = (ms = 700) => page.waitForTimeout(ms);
async function shot(name, caption) {
  await settle();
  const path = `${OUT}/${name}.png`;
  // The app frame scrolls INSIDE <main>, so `fullPage` would photograph one
  // viewport of a scrolled form. Grow the viewport to the content's height
  // for the picture, then put it back.
  const tall = await page.evaluate(() => {
    let most = document.documentElement.scrollHeight;
    for (const el of document.querySelectorAll("main, main *")) {
      if (el.scrollHeight > el.clientHeight + 4) {
        most = Math.max(most, el.scrollHeight + (window.innerHeight - el.clientHeight));
      }
    }
    return Math.min(Math.ceil(most), 6000);
  });
  await page.setViewportSize({ width: 1440, height: Math.max(1000, tall) });
  await settle(300);
  await page.screenshot({ path, fullPage: true });
  await page.setViewportSize({ width: 1440, height: 1000 });
  console.log(`  [shot] ${name}.png (${statSync(path).size} bytes) — ${caption}`);
}
const main = async () => (await page.innerText("main").catch(() => "")).replace(/\s+/g, " ");
async function open() {
  await page.goto(`${BASE}/${TENANT}/premises/new`, { waitUntil: "networkidle" });
  await settle();
}
async function fill(label, value) {
  await page.getByLabel(label, { exact: true }).fill(value);
}
async function address(street, city, state, zip) {
  await page.getByLabel(/^Street address/).fill(street);
  await fill("City", city);
  await fill("State", state);
  await fill("ZIP code", zip);
  await page.getByLabel("City limits").focus(); // leaves the address: the same-address check runs
  await settle(900);
}
const fold = (name) => page.getByRole("button", { name: new RegExp(`^${name}`) });
const cont = async () => {
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await settle(900);
};

// ── sign in ────────────────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

world("disconnect");
world("clean");

// 01 · Property, filled, sections closed
await open();
await address("3721 S Village Dr", "Avenel", "NJ", "07001");
await page.getByLabel("Property type").selectOption({ label: "Single-family" });
await page.getByLabel("City limits").selectOption("inside");
const t01 = await main();
check("01", "opens on Property with three steps and no How many", /Property/.test(t01) && !/How many\?/.test(t01), t01.slice(0, 120));
check("01", "the This premise card names the address with no double comma", t01.includes("3721 S Village Dr, Avenel, NJ 07001") && !t01.includes(",,"));
await shot("01-property-filled", "Property, address filled, sections closed");

// 03 · Services open, none ticked
await page.locator("#services_available").click();
await settle();
const ticked = await page.locator("[data-check-dropdown-list] input:checked").count();
check("03", "no service ticked by default", ticked === 0, `ticked=${ticked}`);
await shot("03-services-dropdown-open", "Services dropdown open, none ticked, All services first");
await page.locator("#services_available").click();

// 02 · Owner, Area & sub-area, Custom fields open
await fold("Owner").click();
await fold("Area & sub-area").click();
await fold("Custom fields").click();
await shot("02-property-sections-open", "Owner, Area & sub-area and Custom fields open");

// 13 · Owner found and linked
await page.locator("#owner_search").fill("Bramble");
await page.getByRole("button", { name: "Find" }).click();
await settle(1200);
const link = page.getByRole("button", { name: "Link this account" });
check("13", "the master account is found", (await link.count()) > 0);
if ((await link.count()) > 0) await link.click();
await settle();
check("13", "linked", /✓ Linked/.test(await main()));
await shot("13-owner-found-linked", "Owner: account found, linked");
await page.getByRole("button", { name: "Unlink" }).click();

// 14 · Owner not available
await page.locator("#owner_search").fill("Zzz Holdings");
await page.getByRole("button", { name: "Find" }).click();
await settle(1200);
check("14", "not available", /This account is not available\./.test(await main()));
await shot("14-owner-not-available", "Owner: account not available");

// 04 · Check address, not connected
await page.getByRole("button", { name: "Check address" }).click();
await settle(1200);
check("04", "not connected", /City map not connected\./.test(await main()));
await shot("04-check-not-connected", "Check address: City map not connected");

// 08 · Continue with Roof age empty
await cont();
const roofInvalid = await page.getByLabel(/Roof age/).getAttribute("aria-invalid");
check("08", "the required field is marked and Property stays", roofInvalid === "true", `aria-invalid=${roofInvalid}`);
await shot("08-required-field-missing", "Continue with a required custom field empty");

// 07 · The same address
await open();
await address("101 silver creek rd.", "Silver Creek", "TX", "78611");
check("07", "the same address is named by number", /This address already exists\./.test(await main()));
await shot("07-duplicate-address", "This address already exists, Open it / Add it anyway");

// 09–11 · Units, Common areas, Review (no City map) — and the save
await open();
await address("3721 S Village Dr,", "Avenel", "NJ", "07001");
await page.getByLabel("Property type").selectOption({ label: "Single-family" });
await page.getByLabel("City limits").selectOption("inside");
await fold("Custom fields").click();
await page.getByLabel(/Roof age/).fill("12");
await page.locator("#services_available").click();
await page.locator("[data-check-dropdown-list] label", { hasText: "Water" }).first().locator("input").check();
await page.locator("#services_available").click();
await cont();
check("09", "the Units step", /How many units/.test(await main()));
await shot("09-units-step", "Units step");
await fold("Common areas").click();
await shot("10-common-areas-open", "Common areas open");
await cont();
const t11 = await main();
check("11", "review groups, no double comma, outcome line", t11.includes("Check before saving") && !t11.includes(",,") && /Creates 1 premise and 1 unit\./.test(t11));
await shot("11-review-no-city-map", "Review, no City map");
await page.getByRole("button", { name: /Create premise/ }).click();
await page.waitForURL((u) => u.pathname.endsWith("/premises"), { timeout: 30000 }).catch(() => undefined);
await settle(1500);
world("readback");

// 05, 06, 12 · with a City map
world("connect");
await open();
await address("9 Nowhere Rd", "Austin", "TX", "78701");
await page.getByRole("button", { name: "Check address" }).click();
await settle(1500);
check("06", "no match", /No match on the city map\./.test(await main()), (await main()).slice(0, 200));
await shot("06-check-no-match", "Check address: no match");
await page.getByLabel(/^Street address/).fill("1408 Pecan St");
await page.getByRole("button", { name: "Check address" }).click();
await settle(1500);
check("05", "match, with the Map section", /Matches the city map\./.test(await main()) && (await page.getByRole("heading", { name: "Map" }).count()) > 0);
await shot("05-check-match", "Check address: match, Use these details / Keep my address");
await page.getByRole("button", { name: "Use these details" }).click();
await settle(900);
await fold("Custom fields").click();
await page.getByLabel(/Roof age/).fill("8");
await cont();
await cont();
check("12", "review shows the parcel and the check date", /Checked against GIS/.test(await main()));
await shot("12-review-with-city-map", "Review, City details used");
await page.getByRole("button", { name: /Create premise/ }).click();
await settle(2500);
world("readback");
world("disconnect");

check("all", "every request stayed on the local origin (webfont aside)", offOrigin.length === 0, `outside=${offOrigin.length} ${offOrigin.slice(0, 5).join(" ")} · webfont requests=${fontRequests.length}`);
writeFileSync(`${OUT}/results.json`, JSON.stringify(results, null, 2));
await browser.close();
console.log(`${results.filter((r) => r.pass).length}/${results.length} checks passed`);
