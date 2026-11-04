// ── Trace ──────────────────────────────────────────────
// Defects: DEF-MET-6118 — the build's only *Add service* control posted the
//          literal `{ service: "water" }`: one service, always water, on a door
//          that takes any of the tenant's enabled services and a unit id.
//          DEF-MET-6108 — a committed build left no `connection_services` row,
//          so its own record read `UNITS 0 · ACTIVATED 0 of 0 · 0 of 0 points
//          live` over eight units and sixteen meters.
// Rules:   CLAUDE.md hard-won law 6 — *"diff the running app against the
//          prototype; no gate in this repo reads rendered output"*, so this
//          script and a person are the only things that can say the control
//          offers the right list · law 2 (an eleventh service must appear on
//          screen ON ITS OWN) · PO ruling 2026-09-21 (*"here filter only active
//          Utility services for that Tenant"*)
// ───────────────────────────────────────────────────────
//
// WHAT IT PROVES, AND WHY EACH HALF NEEDS THE OTHER
// -------------------------------------------------
// 1 · The record of a build committed through the wizard reads TRUE figures —
//     `DEF-MET-6108`. Counted from the record's own payload and compared with
//     what is drawn, so a screen that renders a stale zero cannot pass.
// 2 · *Add service* offers the tenant's ENABLED services, by equality against
//     `GET /settings/services` — `DEF-MET-6118`. A `toContain` would pass on
//     the defect itself, which offered water and nothing else.
// 3 · **A THIRD SERVICE IS SWITCHED ON MID-WALK AND THE CONTROL MUST GROW.**
//     This is the half that cannot be faked: nothing in the front end names
//     `fire`, so if the picker offers it after the tenant enables it, the list
//     is genuinely the server's. It runs against an isolated clone and the
//     service is switched back off at the end.
// 4 · Adding one posts the clerk's own choice and the tiles MOVE, which is the
//     two defects meeting: the control writes a row and the record counts it.
//
// ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING** — it writes a service
// row and toggles a tenant service. `10-scripts/proof-db.sh clone <label>`.
//
// RUN:  BASE=http://127.0.0.1:8977 PREMISES=<uuid> \
//       node 10-scripts/def_met_6118_add_service_walkthrough.mjs
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..");
const require = createRequire(path.join(ROOT, "07-frontend/package.json"));
const { chromium } = require("playwright-core");

const BASE = process.env.BASE || "http://127.0.0.1:8977";
const T = process.env.TENANT || "brazosbend";
const EMAIL = process.env.EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD || "S3cure!passw0rd";
const PREMISES = process.env.PREMISES || "";
const CHROME = process.env.CHROME || "/opt/pw-browsers/chromium";
const SHOTS = process.env.SHOTS || "/tmp/claude-0/rec1-add-service";
/** The service switched on mid-walk. Named HERE and nowhere in `src/`. */
const THIRD = process.env.THIRD || "fire";
mkdirSync(SHOTS, { recursive: true });

let pass = 0;
const failures = [];
const ok = (w) => { pass += 1; console.log(`  ✓ ${w}`); };
const bad = (w, saw) => { failures.push(`${w} — saw: ${saw}`); console.log(`  ✗ ${w}\n      saw: ${saw}`); };
const is = (c, w, saw) => (c ? ok(w) : bad(w, saw));

async function main() {
  if (!PREMISES) throw new Error("PREMISES=<uuid of the premises the build stands on>");
  const browser = await chromium.launch({ executablePath: CHROME });
  const ctx = await browser.newContext();
  const page = await ctx.newPage({ viewport: { width: 1440, height: 1600 } });
  page.setDefaultTimeout(25000);
  const pageErrors = [];
  page.on("pageerror", (e) => pageErrors.push(e.message));

  await page.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await Promise.all([
    page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
    page.click('button[type="submit"]'),
  ]);
  console.log(`signed in as ${EMAIL}`);

  /** Any API call, through the BROWSER's own session — no second auth path. */
  const api = (p2, init) =>
    page.evaluate(
      async ([u, i]) => {
        const r = await fetch(u, {
          credentials: "include",
          headers: { Accept: "application/json", "Content-Type": "application/json" },
          ...(i || {}),
        });
        return { status: r.status, body: await r.text() };
      },
      [`${BASE}/api/${T}${p2}`, init],
    );

  const openBuildTab = async () => {
    await page.goto(`${BASE}/${T}/premises/${PREMISES}?tab=build`, {
      waitUntil: "domcontentloaded",
    });
    await page.waitForSelector("[data-build-tab]", { timeout: 25000 });
    await page.waitForTimeout(1200);
  };

  const openTheChooser = async () => {
    // ⚠ **THE FIVE UNDRAWN ACTS LIVE BEHIND THE *More actions* DISCLOSURE**,
    // and it is a `<button aria-expanded>` rather than a `<summary>` — the kit
    // rejected `<details>` on purpose (see `components/Disclosure.tsx`). Opened
    // BY NAME, exactly as `cr126_build_record_walk.mjs` does: clicking every
    // collapsed button on the page toggles whatever else happens to be closed,
    // and this script hung for four minutes doing precisely that.
    await page.getByText("More actions", { exact: false }).first().click();
    await page.waitForTimeout(400);
    await page.click('[data-act="addService"]');
    await page.waitForSelector('[data-field="add-service"]', { timeout: 10000 });
  };

  const offered = async () =>
    page.locator('[data-field="add-service"] option').evaluateAll((els) =>
      els.map((e) => e.value),
    );

  // ── 1 · THE RECORD OF A COMMITTED BUILD — `DEF-MET-6108` ─────────────────
  console.log("\n1 · the build's own record, after a commit made in this browser");
  await openBuildTab();
  await page.screenshot({ path: `${SHOTS}/01-tiles.png`, fullPage: true });
  const buildId = JSON.parse((await api(`/premises/${PREMISES}/build`)).body).build.id;
  const record = JSON.parse((await api(`/connections/${buildId}/record`)).body);
  const tiles = record.tiles;
  console.log(`  served tiles: units ${tiles.units} · activated ${tiles.activated.done} of ` +
    `${tiles.activated.total} · points ${tiles.service_points.done} of ${tiles.service_points.total}`);
  is(tiles.units > 0, "the UNITS tile is not zero over a real build", String(tiles.units));
  is(tiles.service_points.total > 0, "the service-point tile counts real points",
    JSON.stringify(tiles.service_points));
  is(tiles.activated.total === tiles.units, "ACTIVATED counts every unit of the build",
    JSON.stringify(tiles.activated));
  // ⚠ **DRAWN, NOT ONLY SERVED.** A screen can render a stale zero over a
  // correct payload, which is the half a JSON check cannot see.
  const drawn = await page.locator("[data-build-section='live-state']").innerText();
  is(drawn.includes(`${tiles.activated.done} of ${tiles.activated.total}`),
    "the ACTIVATED pair the server sent is the pair on screen", drawn.replace(/\n/g, " · "));
  is(drawn.includes(`${tiles.service_points.done} of ${tiles.service_points.total}`),
    "the SERVICE POINTS pair the server sent is the pair on screen", drawn.replace(/\n/g, " · "));

  // ── 2 · WHAT THE CONTROL OFFERS — `DEF-MET-6118` ─────────────────────────
  console.log("\n2 · *Add service* offers what this utility SELLS");
  const enabled = JSON.parse((await api("/settings/services")).body)
    .filter((row) => row.enabled)
    .map((row) => row.service);
  console.log(`  the tenant has enabled: ${enabled.join(" · ")}`);
  await openTheChooser();
  await page.screenshot({ path: `${SHOTS}/02-chooser.png`, fullPage: true });
  const first = await offered();
  is(JSON.stringify(first) === JSON.stringify(enabled),
    "the offered set EQUALS the tenant's enabled set", JSON.stringify(first));
  is(first.length > 1, "it is no longer a list of exactly one", JSON.stringify(first));
  // The units of THIS build, plus the build itself for a per-premise main.
  const units = await page
    .locator('[data-field="add-service-unit"] option')
    .evaluateAll((els) => els.map((e) => e.value));
  is(units[0] === "", "the whole build leads the unit list (a main tap has no unit)",
    JSON.stringify(units));
  is(units.length === record.sections.units.count + 1,
    "every unit of this build is offered", `${units.length - 1} of ${record.sections.units.count}`);

  // ── 3 · A THIRD SERVICE, SWITCHED ON MID-WALK ────────────────────────────
  console.log(`\n3 · the tenant enables ${THIRD}; nothing in src/ names it`);
  const on = await api(`/settings/services/${THIRD}`, {
    method: "PUT",
    body: JSON.stringify({ enabled: true }),
  });
  is(on.status === 200, `PUT /settings/services/${THIRD} accepted`, `${on.status} ${on.body.slice(0, 160)}`);
  await openBuildTab();
  await openTheChooser();
  const grown = await offered();
  await page.screenshot({ path: `${SHOTS}/03-third-service.png`, fullPage: true });
  is(grown.includes(THIRD), `${THIRD} appears ON ITS OWN (hard-won law 2)`, JSON.stringify(grown));
  is(grown.length === first.length + 1, "the list grew by exactly one", JSON.stringify(grown));

  // ── 4 · ADDING ONE WRITES A ROW AND THE TILES MOVE ───────────────────────
  console.log("\n4 · the clerk's own choice is what gets posted, and the record counts it");
  await page.selectOption('[data-field="add-service"]', THIRD);
  await page.selectOption('[data-field="add-service-unit"]', ""); // the whole build
  await page.click('[data-act-confirm="addService"]');
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `${SHOTS}/04-after-adding.png`, fullPage: true });
  const after = JSON.parse((await api(`/connections/${buildId}/record`)).body);
  is(after.header.services.includes(THIRD),
    `the build now carries ${THIRD} — the word the clerk chose, not a literal`,
    JSON.stringify(after.header.services));
  is(after.tiles.service_points.total === tiles.service_points.total + 1,
    "the service-point tile counted the new row",
    `${tiles.service_points.total} → ${after.tiles.service_points.total}`);
  // A per-premise service belongs to the BUILD and to no unit, so the UNITS
  // tile must NOT move — `_unit_counts`' own rule.
  is(after.tiles.units === tiles.units, "a per-premise service moves no unit count",
    `${tiles.units} → ${after.tiles.units}`);

  // ── TIDY UP: the third service goes back off ─────────────────────────────
  const off = await api(`/settings/services/${THIRD}`, {
    method: "PUT",
    body: JSON.stringify({ enabled: false }),
  });
  console.log(`\n  ${THIRD} switched back off: ${off.status}`);

  console.log(`\n  page errors: ${pageErrors.length}`);
  pageErrors.forEach((e) => console.log(`   · ${e}`));
  console.log(`\n${pass} passed, ${failures.length} failed`);
  failures.forEach((f) => console.log(`  · ${f}`));
  console.log(`shots: ${SHOTS}`);
  await browser.close();
  process.exitCode = failures.length === 0 && pageErrors.length === 0 ? 0 : 1;
}

main().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
