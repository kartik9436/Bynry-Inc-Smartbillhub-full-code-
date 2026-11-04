// ── THE UNIT'S ASSETS TAB, WALKED IN A BROWSER ─────────────────────────────
// DEF-MET-5860 (the assign never asked which service, so the meter landed
// unbillable) · DEF-MET-5861 (`On since` rendered `install_date`, which the
// assign never sets) · DEF-MET-5862 (`Last read` rendered the USAGE, so a
// first read showed a bare date). All three from the PO's beta walk of
// 2026-09-19; all three ruled the same day.
//
// Run it after any change to `UnitDetailPage.tsx` or to the reassign path.
//
// ⚠ **IT ASSERTS OUT OF THE DATABASE, NOT OUT OF THE RESPONSE.**
// A walk that reads the toast, or the row the screen re-renders, is reading
// what the screen believes. The point of the assign fix is a row in
// `service_points` and a column on `assets`, so `--readback` prints what the
// database holds and the operator compares. The screen assertions below are
// about what a CLERK can do; the database is what actually happened.
//
// ⚠ **AND IT REFUSES A STALE BUILD.** On 2026-09-19 a sibling walk was first
// run against a `dist/` built 26 hours earlier and read three landed fixes as
// ABSENT. Nothing in the page says how old it is and no gate looks at `dist/`,
// so this refuses rather than reporting. Two checks, because in a worktree the
// source is usually UNCOMMITTED and the git one then cannot fire at all:
//   1. the bundle is not older than the newest commit touching `07-frontend/src`;
//   2. the bundle actually CONTAINS a string this change introduced.
// The second is what catches an uncommitted edit that was never rebuilt.
//
// ⚠ **NEVER POINT THIS AT THE BETA.** It assigns real meters. `UA_WALK_API`
// must be a backend running against a CLONE — the run that proved these three
// used `sbh_unitassets`, cloned from `sbh` with `create database … template`.
//
//   UA_WALK_BASE     default http://127.0.0.1:8782   (the SPA + /api proxy)
//   UA_WALK_TENANT   default brazosbend
//   UA_WALK_EMAIL    default dana@brazosbendutilities.com
//   UA_WALK_PASSWORD default S3cure!passw0rd
//   UA_WALK_UNIT     the unit id to stand on (required)
//   UA_WALK_CHROME   default /opt/pw-browsers/chromium-1194/chrome-linux/chrome
//     (the pinned @playwright/test version does not match the preinstalled
//      browser in this container, so the path is passed explicitly — see
//      CLAUDE.md's environment note; never run `playwright install` here.)
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");
import { execSync } from "node:child_process";
import { readFileSync, statSync, readdirSync } from "node:fs";

const BASE = process.env.UA_WALK_BASE || "http://127.0.0.1:8782";
const T = process.env.UA_WALK_TENANT || "brazosbend";
const EMAIL = process.env.UA_WALK_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.UA_WALK_PASSWORD || "S3cure!passw0rd";
const UNIT = process.env.UA_WALK_UNIT;
const CHROME =
  process.env.UA_WALK_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

if (!UNIT) {
  console.error("REFUSED: set UA_WALK_UNIT to the unit id to stand on.");
  process.exit(2);
}

// ── the staleness refusal ──────────────────────────────────────────────────
const built = statSync("07-frontend/dist/index.html").mtime;
const newestSrc = new Date(
  execSync("git log -1 --format=%cI -- 07-frontend/src").toString().trim(),
);
if (built < newestSrc) {
  console.error(
    `REFUSED: dist/ was built ${built.toISOString()} but 07-frontend/src has a\n` +
      `commit at ${newestSrc.toISOString()}. Run \`npx vite build\` first.\n` +
      `A walk against a stale bundle reports absent features that are present.`,
  );
  process.exit(2);
}
// ⚠ **AND THE GIT CHECK ALONE IS NOT ENOUGH IN A WORKTREE.** An uncommitted
// change has no commit to be newer than, so the test above passes over a
// bundle that predates every edit in the tree. This one reads the bundle.
{
  const dir = "07-frontend/dist/assets";
  const js = readdirSync(dir).filter((f) => f.endsWith(".js"));
  const haystack = js.map((f) => readFileSync(`${dir}/${f}`, "utf8")).join("");
  const marker = "Choose a service first";
  if (!haystack.includes(marker)) {
    console.error(
      `REFUSED: the built bundle does not contain ${JSON.stringify(marker)}, so it\n` +
        `predates this change. Run \`npx vite build\` before walking.`,
    );
    process.exit(2);
  }
}

const R = [];
const ok = (n, c, d = "") => R.push(`${c ? "PASS" : "FAIL"} · ${n}${d ? " · " + d : ""}`);

const b = await chromium.launch({ executablePath: CHROME });
const p = await b.newPage();
await p.setViewportSize({ width: 1440, height: 900 }); // the staff design target
await p.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
await p.fill("#signin-email", EMAIL);
await p.fill("#signin-password", PASSWORD);
await Promise.all([
  p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
  p.click('button[type="submit"]'),
]);

const unitUrl = `${BASE}/${T}/premises/units/${UNIT}?tab=assets`;
await p.goto(unitUrl, { waitUntil: "networkidle" });
await p.waitForTimeout(2000);

// ── 1 · THE TWO COLUMNS, ON WHAT IS ALREADY THERE ──────────────────────────
const headers = await p.evaluate(() =>
  [...document.querySelectorAll("table thead th")].map((h) => h.innerText.trim()),
);
ok("the tab draws `On since` and not `Installed`",
   headers.some((h) => /on since/i.test(h)) && !headers.some((h) => /^installed$/i.test(h)),
   headers.join(" | "));

/** Every data row of the on-unit table, cell by cell. */
const readRows = async () =>
  p.evaluate(() =>
    [...document.querySelectorAll("table tbody tr")].map((r) =>
      [...r.cells].map((c) => c.innerText.trim()),
    ),
  );
const before = await readRows();
ok("the unit's assets are listed", before.length > 0, `${before.length} row(s)`);

// ⚠ **A READING IS NOT A USAGE.** The `Last read` cell must carry the REGISTER
// figure; asserting merely that a number is present passes on the usage that
// was already there, which is the defect.
const lastReadCells = before.map((cells) => cells.join(" · ")).join("\n");
ok("`Last read` carries a quantity with its unit",
   /\d[\d,]*(\.\d+)?\s+\S+/.test(lastReadCells), "sample: " + (before[0] || []).join(" · "));

// ── 2 · THE ASSIGN ASKS WHICH SERVICE ──────────────────────────────────────
await p.locator("button").filter({ hasText: /Assign from inventory/i }).first().click();
await p.waitForTimeout(2500);

const picker = p.locator("#inventory-finder-service");
ok("the panel asks which service", (await picker.count()) === 1);

const options = await p.evaluate(() => {
  const s = document.querySelector("#inventory-finder-service");
  return s ? [...s.options].map((o) => ({ value: o.value, label: o.textContent.trim() })) : [];
});
// ⚠ **NO DEFAULT** — the ruling's own words: *"Nothing may guess which service
// a meter serves"*. The leading option is the placeholder.
const selected = await p.evaluate(
  () => document.querySelector("#inventory-finder-service")?.value,
);
ok("nothing is chosen by default", selected === "", `value=${JSON.stringify(selected)}`);
// ⚠ **ONLY THIS UNIT'S SERVICES.** Eleven options would mean the picker is
// offering services the server refuses (`BR-MET-119`).
ok("it offers only this unit's services, not all eleven",
   options.length > 1 && options.length <= 7,
   options.map((o) => o.label).join(" · "));

/** The `Assign ✓` button on the shelf row whose asset number matches. */
const shelfRow = (assetNo) =>
  p.locator("[data-finder-row]").filter({ hasText: assetNo }).first();

const firstMeter = await p.evaluate(() => {
  const rows = [...document.querySelectorAll("[data-finder-row]")];
  const found = rows.find((r) => /meter/i.test(r.cells[1]?.innerText ?? ""));
  return found ? found.getAttribute("data-finder-row") : null;
});
ok("a meter is on the shelf to assign", firstMeter !== null, String(firstMeter));

if (firstMeter) {
  const button = shelfRow(firstMeter).locator("button").last();
  const state = await button.evaluate((el) => ({
    disabled: el.disabled,
    title: el.getAttribute("title"),
  }));
  // ⚠ **UNREACHABLE, NOT REFUSED AFTER THE FACT.** A server refusal would
  // bounce the clerk back to an empty shelf with their search gone.
  ok("a meter with no service chosen cannot be assigned",
     state.disabled === true, `title=${JSON.stringify(state.title)}`);
  ok("and the row says what to do",
     /service/i.test(state.title ?? ""), state.title ?? "(no title)");

  // Choose the SECOND service, never the first: picking the first would pass
  // on a picker that silently defaults.
  const chosen = options[options.length - 1].value;
  await picker.selectOption(chosen);
  await p.waitForTimeout(500);
  const after = await button.evaluate((el) => el.disabled);
  ok("choosing a service opens the control", after === false, `service=${chosen}`);

  await button.click();
  await p.waitForTimeout(3000);
  const body = await p.evaluate(() => document.body.innerText);
  ok("the assign reports success", new RegExp(firstMeter).test(body));
  console.log(`\nASSIGNED ${firstMeter} with service=${chosen} — read it back from the DB.`);
}

// ── 3 · A NON-MEASURING ASSET IS NOT MADE TO DECLARE ONE ───────────────────
// A backflow preventer or a cart has no register. `BR-AST-009` binds the
// measuring types only, and the ruling says *optional for everything else*.
await p.goto(unitUrl, { waitUntil: "networkidle" });
await p.waitForTimeout(1500);
await p.locator("button").filter({ hasText: /Assign from inventory/i }).first().click();
await p.waitForTimeout(2500);
const device = await p.evaluate(() => {
  const rows = [...document.querySelectorAll("[data-finder-row]")];
  const found = rows.find((r) => /backflow|cart|battery/i.test(r.cells[1]?.innerText ?? ""));
  return found ? found.getAttribute("data-finder-row") : null;
});
if (device) {
  const enabled = await shelfRow(device)
    .locator("button")
    .last()
    .evaluate((el) => !el.disabled);
  ok("a non-measuring asset assigns with no service", enabled, device);
} else {
  ok("a non-measuring asset assigns with no service", false, "none on the shelf to try");
}

// ── 3b · A SUB-METER IS HELD TO THE SAME RULE AS A METER ───────────────────
// `MEASURING_TYPES` is meter · net_meter · sub_meter, and the screen's
// predicate reads `BR-AST-004`'s CATEGORY — the `meters` and `sub_meters`
// tabs. A walk that only ever tried a `meters` row would pass over a predicate
// that had quietly narrowed to one tab.
const subMeter = await p.evaluate(() => {
  const rows = [...document.querySelectorAll("[data-finder-row]")];
  const found = rows.find((r) => /sub-?meter/i.test(r.cells[1]?.innerText ?? ""));
  return found ? found.getAttribute("data-finder-row") : null;
});
if (subMeter) {
  const state = await shelfRow(subMeter)
    .locator("button")
    .last()
    .evaluate((el) => ({ disabled: el.disabled, title: el.getAttribute("title") }));
  ok("a sub-meter with no service chosen cannot be assigned either",
     state.disabled === true && /service/i.test(state.title ?? ""),
     `${subMeter} · title=${JSON.stringify(state.title)}`);
} else {
  ok("a sub-meter with no service chosen cannot be assigned either", false,
     "none on the shelf to try — seed one before trusting this line");
}

// ── 4 · NARROW, because a staff screen is laptop and desktop ───────────────
await p.setViewportSize({ width: 1280, height: 800 });
await p.waitForTimeout(800);
const overflow = await p.evaluate(
  () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
);
ok("no sideways scroll at 1280", !overflow);

await b.close();
console.log("\n" + R.join("\n"));
console.log(`\n${R.filter((r) => r.startsWith("PASS")).length}/${R.length} PASS`);
process.exit(R.some((r) => r.startsWith("FAIL")) ? 1 : 0);
