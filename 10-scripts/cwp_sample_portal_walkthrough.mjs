// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-069 · US-CWP-070 · US-CWP-071..074 · US-CWP-016..018 —
//           the portal a FRESHLY PROVISIONED utility gets, in a browser.
// Rules:    PO ruling 2026-09-07: *"before step 29 this - you ahve to set all
//           the self service data in settings -> configure -> Customer portal -
//           {overview, branding, Help & Answer, Tips  + service centers }"* ·
//           PO standing definition of done: *"everything should be executed
//           based on actual code … also ensure you do web walkthorugh before
//           you sign off the user story or build"* · CLAUDE.md hard-won law 6
//           (no gate reads rendered output)
// Impacts:  apps/tenancy/portal_sample.py · apps/portal/sample_data.py
// ───────────────────────────────────────────────────────
/**
 * cwp_sample_portal_walkthrough — the five things the ruling names, ON SCREEN,
 * on a tenant that signed up through the real path and was seeded by nobody.
 *
 *     # a database nobody else is seeding
 *     eval "$(10-scripts/proof-db.sh clone cwpseed --export)"
 *     # provision a tenant through the REAL sign-up endpoint
 *     curl -X POST $API/api/tenants -d '{…}'
 *     # then, with the backend and the built bundle up:
 *     PORTAL_TENANT=riverbend-water node 10-scripts/cwp_sample_portal_walkthrough.mjs
 *
 * ⚠ **IT IS NOT A SECOND COPY OF `cwp_portal_walkthrough.mjs`, AND THAT ONE
 * SHOULD BE RUN TOO.** That script opens all 50 portal screens and is already
 * parameterised by `PORTAL_TENANT` / `PORTAL_LOGIN` / `PORTAL_PASSWORD`, so it
 * runs against a freshly provisioned tenant unchanged — run it for coverage.
 * This one asks a different question, which no existing check asks: **did the
 * SAMPLE SET put anything in the portal at all?** It fails when a screen is
 * technically fine and EMPTY, which is exactly the state every provisioned
 * tenant was in until 2026-09-07 and which a screen-by-screen walk reads as a
 * clean run.
 *
 * ⚠ **REBUILD THE BUNDLE BEFORE YOU WALK.** `server.mjs` serves whatever was in
 * `dist/` when it started, forever, and prints the directory only at boot.
 *
 * ⚠ **`playwright` IS RESOLVED FROM `07-frontend`, EXPLICITLY.** Node resolves a
 * bare import from the SCRIPT's own directory upward, never from the working
 * directory, and the repo root has no `node_modules`.
 *
 * Exit code 1 when any check fails, and every failure names what it wanted.
 */
import { createRequire } from "node:module";
import { existsSync } from "node:fs";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:4299";
const TENANT = process.env.PORTAL_TENANT ?? "riverbend-water";
const LOGIN = process.env.PORTAL_LOGIN ?? "";
const PASSWORD = process.env.PORTAL_PASSWORD ?? "Sample-Portal-2026!";
const CHROME = process.env.PW_CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

const rel = (p) => `/${TENANT}/portal` + (p === "/" ? "" : p);
const browser = await chromium.launch(existsSync(CHROME) ? { executablePath: CHROME } : {});
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });

const failures = [];
const notes = [];
const throttled = [];
page.on("pageerror", (e) => failures.push(`JS ERROR ${page.url()}: ${e.message.slice(0, 160)}`));
page.on("response", (r) => {
  // ⚠ A `429` ON THE GUEST SURFACE IS THIS SCRIPT'S OWN DOING, NOT A DEFECT.
  // `PortalTenantThrottle` limits an anonymous visitor per address, and a
  // walkthrough opens six guest pages faster than any person would. Reporting
  // it as a product failure is a check that fails for a reason it invented —
  // so it is COUNTED and named at the end rather than raised as a fault.
  if (r.status() === 429) return throttled.push(r.url().replace(BASE, ""));
  if (r.status() >= 400 && r.url().includes("/api/")) failures.push(`${r.status()} ${r.url().replace(BASE, "")}`);
});

//: ⚠ **THE GUEST SURFACE IS THROTTLED PER ADDRESS** (`PortalTenantThrottle`),
//: so a walkthrough that opens six guest pages back to back earns itself a
//: `429` and then reports it as a product failure. A pause between pages is
//: the honest fix; raising the throttle for a test would prove less.
const PAUSE = Number(process.env.PORTAL_PAUSE ?? 1500);

async function open(path) {
  await page.waitForTimeout(PAUSE);
  // ⚠ NOT `networkidle` — the portal shell holds a connection open, so it never
  // settles and every goto burns its whole timeout in silence.
  await page.goto(BASE + path, { waitUntil: "domcontentloaded", timeout: 20000 }).catch(() => {});
  await page.waitForSelector("[data-screen], main", { timeout: 10000 }).catch(() => {});
  await page.waitForTimeout(600);
  // ⚠ **WAIT FOR THE LOADING LINE TO GO, NEVER FOR A FIXED NUMBER OF SECONDS.**
  // `/usage` fetches a year of readings after mount and shows *Reading your
  // usage…* until they land. A fixed sleep read that line as a screen with no
  // tip on it and reported a FAILED CHECK over a tip the API was serving
  // correctly — twice, at 0.7s and again at 1.6s, which is the tell: a check
  // whose verdict moves with the machine's load is not measuring the product.
  const LOADING = /Reading your usage|Loading|…\s*$/;
  for (let i = 0; i < 25; i += 1) {
    const now = (await page.locator("body").innerText().catch(() => "")).trim();
    if (!LOADING.test(now)) return now;
    await page.waitForTimeout(400);
  }
  return (await page.locator("body").innerText().catch(() => "")).trim();
}

function want(label, ok, saw) {
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${label}`);
  if (!ok) failures.push(`${label} — saw: ${String(saw).replace(/\s+/g, " ").slice(0, 220)}`);
}

console.log(`\n── the portal a fresh ${TENANT} actually serves ──`);

// ── 1 · the front page is LIVE and BRANDED, not the holding page ──────────
const front = await open(rel("/"));
want("the portal is live (not the holding page)", !/not (yet )?open|holding/i.test(front) && front.length > 120, front.slice(0, 200));
want("the strapline is on the front page", front.includes("meter readings"), front.slice(0, 400));
const api = await (await page.request.get(BASE + `/api/${TENANT}/portal/public/front`)).json().catch(() => ({}));
want("the front payload says is_live", api.is_live === true, JSON.stringify(api).slice(0, 200));
want("the front page offers the tenant's own services", (api.services ?? []).length > 0, JSON.stringify(api.services));
want("office hours are set", Boolean(api.office_hours_text), api.office_hours_text);
want("an emergency number is set", Boolean(api.emergency_phone), api.emergency_phone);
want("the Help door is on", api.links?.help === true, JSON.stringify(api.links));
want("the Visit-us door is on", api.links?.visit === true, JSON.stringify(api.links));
notes.push(`front page services: ${(api.services ?? []).map((s) => s.name ?? s.code).join(", ")}`);

// ── 2 · Help & answers — a list, and an answer that opens ─────────────────
const help = await open(rel("/help"));
want("the help page lists at least one question", /\?/.test(help), help.slice(0, 300));
const answers = await (await page.request.get(BASE + `/api/${TENANT}/portal/public/help`)).json().catch(() => ({}));
const list = answers.answers ?? answers.results ?? answers;
want("the help API serves published answers", Array.isArray(list) && list.length > 0, JSON.stringify(answers).slice(0, 200));
if (Array.isArray(list) && list.length) {
  notes.push(`published answers: ${list.length}`);
  const slug = list[0].slug;
  const one = await open(rel(`/help/${slug}`));
  want("an answer opens and has a body a customer can read", one.length > 200, one.slice(0, 200));
}

// ── 3 · service centres — a counter, with its opening hours ───────────────
const visit = await open(rel("/visit"));
want("the visit page lists at least one counter", /office|counter|centre|center/i.test(visit), visit.slice(0, 300));
//: ⚠ `service-centres`, NOT `centres`. The first draft of this file guessed
//: the shorter spelling, got `{}` from a 404 and reported a FAILED CHECK over
//: three service centres that were sitting in the database — a check looking
//: at the wrong thing (CLAUDE.md law 7). The route list is in `config/urls.py`.
const centres = await (await page.request.get(BASE + `/api/${TENANT}/portal/public/service-centres`)).json().catch(() => ({}));
const clist = centres.centres ?? centres.results ?? centres;
want("the centres API serves at least one shown centre", Array.isArray(clist) && clist.length > 0, JSON.stringify(centres).slice(0, 200));
if (Array.isArray(clist) && clist.length) {
  notes.push(`counters shown to customers: ${clist.length}`);
  const one = await open(rel(`/visit/${clist[0].slug}`));
  // A counter with no hours is not a counter a person can walk into.
  want("the counter shows its opening hours", /\d{1,2}[:.]\d{2}|closed/i.test(one), one.slice(0, 400));
  want("the counter shows an address", /\d+\s+\w/.test(one), one.slice(0, 400));
}

// ── 4 · the seeded customer can actually sign in ──────────────────────────
if (!LOGIN) {
  failures.push("PORTAL_LOGIN was not set — nothing proved about the login half");
} else {
  const signIn = await page.request.post(BASE + `/api/${TENANT}/portal/auth/sign-in`, {
    data: { email: LOGIN, password: PASSWORD },
  });
  want(`the seeded customer signs in (${LOGIN})`, signIn.ok(), `${signIn.status()} ${(await signIn.text()).slice(0, 160)}`);
  if (signIn.ok()) {
    const home = await open(rel("/home"));
    want("the signed-in home page is not the signed-out one", !/signed out/i.test(home), home.slice(0, 200));
    // ── 5 · a tip, on a screen whose tip is in season ─────────────────────
    // The seeded set has six tips on six screens; the `usage` one runs June to
    // September, and the `portal_home` one is deliberately OFF and out of
    // season, so the home page correctly shows no tip container at all.
    const usage = await open(rel("/usage"));
    want("a tip is on screen", /evaporation|toilet|dials|leak|frost|meter is yours/i.test(usage), usage.slice(0, 500));
  }
}

console.log("");
for (const n of notes) console.log(`  · ${n}`);
if (throttled.length) console.log(`  · ${throttled.length} guest request(s) were throttled (429) — this script\u2019s pace, not a fault`);
if (failures.length) {
  console.log(`\n${failures.length} FAILURE(S):`);
  for (const f of failures) console.log(`  ✗ ${f}`);
} else {
  console.log("\nevery check passed — the sample set put a working portal on this tenant");
}
await browser.close();
process.exit(failures.length ? 1 : 0);
