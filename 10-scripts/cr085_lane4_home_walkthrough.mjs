// ── Trace ────────────────────────────────────────────────────────────────
// Change:   CR-085 step 2 lane 4 — HOME AND ACCOUNTS.
// Screens:  CWP-022 `/home` · CWP-023 `/accounts` · CWP-020 `/accounts/add` ·
//           CWP-065 `/account` · CWP-024 `/my-details` · CWP-025
//           `/my-details/preferences` · CWP-001 `/` (the redirect)
// Defects:  DEF-CWP-4899 (thirty strings in no catalogue) · DEF-CWP-4900 (a
//           signed-in customer served the guest front page at the address a
//           utility prints on its bills) · DEF-CWP-4901 (CWP-065 had one
//           inbound link) · DEF-CWP-4905 (at 390 the accounts table put
//           BALANCE and STATUS off the right edge; + Add an account twice) ·
//           DEF-CWP-4906 part (the drawn NOTHING DUE state) · DEF-CWP-4935
//           (the language sentence that was false) · DEF-CWP-4941 (THIS
//           FILE: its own readiness wait, which stopped meaning "ready" the day
//           R-10 and R-22 put the screen mark on the reading branch)
// Rules:    R-10 · R-22 (PO 2026-09-11) · B14 rule 39 (the anchors it reads) ·
//           CLAUDE.md hard-won law 6 (no gate in this repo reads rendered
//           output) · law 7 (a check's output must distinguish pass from fail
//           TO A READER, not merely by exit code)
// ─────────────────────────────────────────────────────────────────────────
//
// WHY THIS FILE EXISTS AND WHAT IT CANNOT DO
// ------------------------------------------
// Every defect it checks passed `tsc`, eslint, 939 portal test cases and every
// gate before it was found, because none of those reads rendered output. This
// is the instrument that does, and it is a person with a browser wearing a
// script — `10-scripts/*_walkthrough.mjs` has 30-odd worked examples.
//
// ⚠ IT CANNOT PROVE THE PHONE LAYOUT IS *RIGHT*, only that the two halves swap.
// jsdom applies no CSS, so the DOM tests beside these screens see BOTH the
// table and the card list at once; this is the only place the `max-md:` switch
// is real. What it still cannot tell you is whether the card READS well, which
// is why the close-out is a person looking at it.
//
// ⚠ IT NEEDS A SIGNED-IN CUSTOMER, AND THAT IS THE HARD PART. Pass the
// credential in the environment; there is no default, because a password baked
// into a repo file is a password in the repo.
//
//     SBH_BASE=http://127.0.0.1:8414 SBH_TENANT=brazosbend \
//     SBH_EMAIL=… SBH_PASSWORD=… node 10-scripts/cr085_lane4_home_walkthrough.mjs
//
// ⚠ RUN IT AGAINST YOUR OWN SERVER, NOT THE SHARED ONE. `PORT=<free> \
// API_PROXY_TARGET=http://127.0.0.1:8000 node 07-frontend/server.mjs` over your
// worktree's own `dist`. The shared stack on :8401 is several lanes' at once.
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const requireFrontend = createRequire(path.resolve("07-frontend/package.json"));
const { chromium } = requireFrontend("playwright-core");

/** Any installed chromium, not only the revision playwright pinned. */
function findChromium() {
  if (process.env.SBH_CHROMIUM) return process.env.SBH_CHROMIUM;
  const wanted = chromium.executablePath();
  if (fs.existsSync(wanted)) return wanted;
  const root = process.env.PLAYWRIGHT_BROWSERS_PATH ?? "/opt/pw-browsers";
  for (const dir of fs.existsSync(root) ? fs.readdirSync(root) : []) {
    // ⚠ `chromium` is a FILE in this image and `chromium-1194` is the
    // directory; a helper that returns the first name starting with "chromium"
    // hands playwright a path that is not an executable.
    if (!dir.startsWith("chromium")) continue;
    for (const rel of ["chrome-linux/chrome", "chrome"]) {
      const candidate = path.join(root, dir, rel);
      if (fs.existsSync(candidate)) return candidate;
    }
  }
  return wanted; // let playwright report the miss in its own words
}

const BASE = process.env.SBH_BASE ?? "http://127.0.0.1:8414";
const TENANT = process.env.SBH_TENANT ?? "brazosbend";
const EMAIL = process.env.SBH_EMAIL;
const PASSWORD = process.env.SBH_PASSWORD;
if (!EMAIL || !PASSWORD) {
  console.error("SBH_EMAIL and SBH_PASSWORD are required — this walk is of the SIGNED-IN portal.");
  process.exit(2);
}

// ⚠ **THE THIRD COLUMN IS THE POINT, AND IT IS A DEFECT THIS FILE CAUSED IN
// ITSELF (`DEF-CWP-4941`).** Waiting for `[data-screen="…"]` used to mean *the
// screen has its data*, because the mark was only on the success branch. R-10 and
// R-22 changed that: a screen must keep its identity while it is READING and when
// it has FAILED, so `Home.tsx` and `MyAccounts.tsx` now carry the mark on all
// three branches — which is right, and it silently turned every
// `waitForSelector('[data-screen=…]')` in this file into a race.
//
// It did not fail honestly. On a quiet machine the read finishes first and every
// check passes; under load the same code reports `cardsShown: null,
// tableShown: null` and two FAILs that name a layout defect which is not there.
// **A check whose answer depends on the load average is not a check** — it is the
// *what would make this pass wrongly* question (law 7) with both answers yes.
//
// So each route names a mark that exists ONLY once its data is drawn. `null` means
// there is no such branch on that screen and the id mark is already conclusive.
const ROUTES = [
  ["/home", "CWP-022", "[data-testid='home-account']"],
  ["/accounts", "CWP-023", "[data-accounts-cards], [data-list='CWP-023']"],
  ["/accounts/add", "CWP-020", null],
  ["/account", "CWP-065", null],
  ["/my-details", "CWP-024", null],
  ["/my-details/preferences", "CWP-025", null],
];

let failures = 0;
let checks = 0;
function check(ok, what, saw) {
  checks += 1;
  if (ok) {
    console.log(`  PASS  ${what}`);
  } else {
    failures += 1;
    console.log(`  FAIL  ${what}${saw === undefined ? "" : `  — saw ${JSON.stringify(saw)}`}`);
  }
}

const browser = await chromium.launch({ executablePath: findChromium() });
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await context.newPage();
const jsErrors = [];
page.on("pageerror", (e) => jsErrors.push(e.message));

// ── sign in ───────────────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/portal/sign-in`, { waitUntil: "domcontentloaded" });
await page.fill("#portal-email", EMAIL);
await page.fill("#portal-password", PASSWORD);
await page.click('button:has-text("Sign in")');
await page.waitForURL(/\/portal\/home$/, { timeout: 30_000 });
console.log(`signed in, landed on ${page.url()}`);

for (const width of [1280, 390]) {
  await page.setViewportSize({ width, height: width === 390 ? 840 : 900 });
  console.log(`\n══ ${width}px ═══════════════════════════════════════════════`);

  for (const [route, screen, settled] of ROUTES) {
    await page.goto(`${BASE}/${TENANT}/portal${route}`, { waitUntil: "domcontentloaded" });
    await page.waitForSelector(`[data-screen="${screen}"]`, { timeout: 30_000 });
    // ⚠ `state: "attached"` AND NOT THE DEFAULT `"visible"`. This screen draws
    // BOTH halves of the 390/1280 split and hides one with `max-md:`, so a comma
    // selector resolves to two elements and playwright "proceeds with the first
    // one" — the card list, which is `display: none` at 1280. Waiting for it to
    // be VISIBLE can therefore never succeed at the desktop width: a wait that is
    // incapable of passing, which is the same law-7 shape as the race it replaces,
    // one turn later. What this wait actually asks is *has the data been drawn*,
    // and that is attachment.
    if (settled) await page.waitForSelector(settled, { timeout: 30_000, state: "attached" });
    const seen = await page.evaluate(() => ({
      // The page body NEVER scrolls sideways. A table may, inside its own box.
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    }));
    console.log(`${route} (${screen})`);
    check(
      seen.scrollWidth <= seen.clientWidth,
      `${route} — the page body does not scroll sideways`,
      seen,
    );
  }

  // `DEF-CWP-4905` — the two facts the accounts screen exists to answer.
  await page.goto(`${BASE}/${TENANT}/portal/accounts`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector('[data-screen="CWP-023"]');
  // The screen mark is on the READING branch too — wait for the data (see ROUTES).
  await page.waitForSelector("[data-accounts-cards], [data-list='CWP-023']", {
    timeout: 30_000,
    state: "attached", // both halves exist at both widths; one is hidden. See ROUTES.
  });
  const accounts = await page.evaluate(() => {
    const cards = document.querySelector("[data-accounts-cards]");
    const table = document.querySelector("[data-list='CWP-023']");
    const shown = (el) => (el ? getComputedStyle(el).display !== "none" : null);
    return {
      cardsShown: shown(cards),
      // The table's own wrapper carries `max-md:hidden`, not the list div.
      tableShown: shown(table?.parentElement ?? null),
      addDoors: [...document.querySelectorAll("a")].filter((a) =>
        (a.getAttribute("href") ?? "").endsWith("/accounts/add"),
      ).length,
    };
  });
  check(
    width === 390 ? accounts.cardsShown === true : accounts.cardsShown === false,
    `accounts — the phone half is ${width === 390 ? "shown" : "hidden"} at ${width}`,
    accounts,
  );
  check(
    width === 390 ? accounts.tableShown === false : accounts.tableShown === true,
    `accounts — the table is ${width === 390 ? "hidden" : "shown"} at ${width}`,
    accounts,
  );
  // ⚠ A COUNT, NOT A PRESENCE. `+ Add an account` was drawn once and built
  // twice; a check asking *does the door exist* passed on both copies.
  check(accounts.addDoors === 1, "accounts — exactly ONE + Add an account door", accounts.addDoors);
}

// ── `DEF-CWP-4900` — the address a utility prints on its bills ────────────
await page.setViewportSize({ width: 1280, height: 900 });
await page.goto(`${BASE}/${TENANT}/portal`, { waitUntil: "domcontentloaded" });
// ⚠ Wait for ANY screen mark rather than for CWP-022: waiting for the id this
// check is about would make the check unable to fail — the redirect breaking and
// the wait timing out would look the same. A guest page carries one too.
await page.waitForSelector("[data-screen]", { timeout: 30_000, state: "attached" });
const root = await page.evaluate(() => ({
  url: location.pathname,
  screen: document.querySelector("[data-screen]")?.getAttribute("data-screen") ?? null,
  errands: document.querySelectorAll("[data-errand]").length,
}));
check(root.screen === "CWP-022", "/portal opens the customer's home when signed in", root);
check(root.errands === 0, "/portal draws no guest errand grid when signed in", root);

// ── `DEF-CWP-4901` — the door the drawing puts on Home ────────────────────
await page.goto(`${BASE}/${TENANT}/portal/home`, { waitUntil: "domcontentloaded" });
await page.waitForSelector('[data-screen="CWP-022"]');
// Same race: `home-balance` is the mark on the reading state as well, so the one
// to wait for is the account CARD, which only the success branch draws.
await page.waitForSelector("[data-testid='home-account']", { timeout: 30_000, state: "attached" });
const home = await page.evaluate((tenant) => {
  const doors = [...document.querySelectorAll("[data-testid='home-account'] a")].map((a) => ({
    text: a.textContent?.trim(),
    href: a.getAttribute("href"),
  }));
  return {
    doors,
    wanted: `/${tenant}/portal/account`,
    paidUp: document.querySelector("[data-home-paid-up]")?.textContent ?? null,
    owing: document.querySelector("[data-owing]")?.textContent ?? null,
    balanceLabel: document.querySelector("[data-kpi='balance']")?.textContent?.trim() ?? null,
  };
}, TENANT);
check(
  home.doors.some((d) => d.href === home.wanted),
  "home — the account card carries the drawn door into CWP-065, by ADDRESS",
  home.doors,
);
// `DEF-CWP-4906` part — nothing owed says so rather than printing a bare $0.00.
if (home.owing === "$0.00") {
  check(home.paidUp !== null, "home — nothing owed draws the NOTHING DUE sentence", home);
} else {
  console.log(`  SKIP  home — the NOTHING DUE state (this fixture owes ${home.owing})`);
}

// ── `DEF-CWP-4935` — the language sentence that was false ────────────────
await page.goto(`${BASE}/${TENANT}/portal/my-details/preferences`, {
  waitUntil: "domcontentloaded",
});
await page.waitForSelector('[data-screen="CWP-025"]');
const why = await page.evaluate(() => {
  const line = document.querySelector("[data-website-language]");
  return line?.nextElementSibling?.textContent?.trim() ?? null;
});
check(
  why === "We send bills in English today; this site follows the language above.",
  "preferences — the language panel says what is TRUE (BR-CWP-107)",
  why,
);

check(jsErrors.length === 0, "no JavaScript error on any screen walked", jsErrors);

console.log(`\n${checks - failures}/${checks} checks passed.`);
if (failures > 0) console.log(`${failures} FAILED — read the lines above, not the exit code.`);
await browser.close();
process.exit(failures === 0 ? 0 : 1);
